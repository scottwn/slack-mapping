import json
import track_notifications
import os
import requests
import time
import re
from requests.auth import HTTPBasicAuth
from get_slack_id import GetSlackID

# global constants:
HOSTNAME = 'http://qa.tptpm.info:8090'
JENKINS = requests.Session()
# 1000000 milliseconds is about 15 minutes, long enough to catch builds that
# took a while.
MAX_AGE = 1000000

# global variables:
current_time = 0
passed_notifications = []

# Generate list of builds from dict returned by Jenkins API:
def parse_build_data(build_data):
    output = []
    for job in build_data['jobs']:
        for build in job['builds']:
            output.append(make_build(build))
    return output

# Check if build contains necessary data and return it:
def make_build(build):
    if (build['changeSet']['items'] and
        # Open paren in build name indicates branch information exists.
        '(' in build['fullDisplayName'] and
        # CodeSize already notifies via GitHub comment.
        'CodeSize' not in build['fullDisplayName']):
        user_url = build['changeSet']['items'][0]['author']['absoluteUrl']
        build_name = build['fullDisplayName']
        return {
            'build': build_name,
            'number': build['number'],
            'result': build['result'],
            'timestamp': build['timestamp'],
            'url': build['url'],
            'author': build['changeSet']['items'][0]['author']['fullName'],
            # Parse Jenkins username from url:
            'user': user_url.split('/')[4],
            # Regex to parse branch name from build:
            'branch': re.split('[()]', build_name)[1],
            'started_by_naginator': started_by_naginator(build['actions']),
            'upstream': upstream(build['actions']),
            # The title of the GitHub issue associated with this Jenkins build
            # is available in the following field in the Jenkins API.
            'title': build['changeSet']['items'][0]['msg']
        }

def started_by_naginator(actions):
    for action in actions:
        if ('causes' in action and
            'Naginator' in action['causes'][0]['shortDescription']):
            return True
    return False

# Return the number of the upstream build of Core-SyntaxCheck-PHP-DevCloud that
# started this build. If the build was started by some other action (some other
# job, CLI, etc.), return 0.
def upstream(actions):
    for action in actions:
        if ('causes' in action and
            'upstream' in action['causes'][0]['shortDescription'] and
            'Syntax' in action['causes'][0]['shortDescription']):
            # Regex to parse number of upstream build from description of cause:
            return int(
                re.sub('[^0-9]',
                '', 
                action['causes'][0]['shortDescription'])
            )
    return 0

# Return True if this is a build of Acceptance that will be re-run by Naginator.
def naginator_check(started_by_naginator, number, name):
    global HOSTNAME, JENKINS
    if 'Acceptance' not in name:
        return False
    if not started_by_naginator:
        return True
    job = '/job/Core-Acceptance-PHP-DevCloud/'
    url = '{}{}{}{}'.format(
        HOSTNAME,
        job,
        str(number),
        '/artifact/naginator_count'
    )
    naginator_count = JENKINS.get(url)
    url = '{}{}{}{}'.format(
        HOSTNAME,
        job,
        str(number),
        '/artifact/naginator_maxcount'
    )
    naginator_maxcount = JENKINS.get(url)
    return naginator_count.json() < naginator_maxcount.json()
        
# Core-SyntaxCheck-PHP-DevCloud triggers 6 builds, listed here in final_builds.
# Check if each of these builds, triggered by the same upstream build, have
# passed:
def all_tests_passed(upstream, builds):
    global passed_notifications
    if upstream == 0 or upstream in passed_notifications:
        return False
    passed_notifications.append(upstream)
    final_builds = [
        'Acceptance',
        'CodeSniff',
        'Unit-JS',
        'Unit-PHP',
        'API-Functional',
        'API-Unit'
    ]
    for final_build in final_builds:
        result = upstream_match(final_build, upstream, builds)
        if not result == 'SUCCESS':
            return False
    return True

# Return the result of a certain build that was triggered by a certain upstream
# build:
def upstream_match(final_build, upstream, builds):
    for build in builds:
        if (build and
            upstream == build['upstream'] and
            final_build in build['build']):
            return build['result']

def append_assignee(output, user):
    if not output:
        return ' cc: @' + user
    return ' @' + user

# If a user has failure notifications and finish notifications turned on, they
# will also be notified about the results of tests for pull requests that they
# are assigned to.
def assignees(title):
    # Lists of assignees are in the GitHub issues API.
    github_api = 'https://api.github.com/repos/TeachersPayTeachers/tpt/issues'
    token_header = 'token ' + os.environ['GITHUB_REPO_TOKEN']
    header = {'Authorization': token_header}
    issues = requests.get(github_api, headers=header).json()
    assignees_list = []
    for issue in issues:
        if not assignees_list and issue['title'] == title:
            assignees_list = issue['assignees']
    output = ''
    for assignee in assignees_list:
        user_url = 'https://api.github.com/users/' + assignee['login']
        user_data = requests.get(user_url, headers=header).json()
        user = GetSlackID(
            user_data['name'],
            user_data['email'],
            assignee['login']
        )
        if user.exists and user.notify_on_failure and user.notify_on_finish:
            output += append_assignee(output, user.slack_name)
    return output

def notify(build, builds):
    email = build['user'] + '@teacherspayteachers.com'
    user = GetSlackID(build['author'], email, build['user'])
    if user.exists:
        # If the user has failure notifications turned on and the build failed
        # and the build is not being re-run by Naginator, then send a failure
        # message:
        if (user.notify_on_failure and
            build['result'] == 'FAILURE' and not
            naginator_check(
                build['started_by_naginator'],
                build['number'],
                build['build']
            )):
            message = (
                build['build'] +
                ' failed: ' +
                build['url'] +
                assignees(build['title'])
            )
            slack(user.slack_name, message)
        # If the user has finish notifications turned on and the build passed,
        # check if the tests that were triggered by the build of SyntaxCheck that
        # triggered this build have also passed, and if so, then send a finish
        # notification:
        if (user.notify_on_finish and
            build['result'] == 'SUCCESS' and
            all_tests_passed(build['upstream'], builds)):
            syntax_job = '/job/Core-SyntaxCheck-PHP-DevCloud/'
            syntax_url = '{}{}{}{}'.format(
                HOSTNAME,
                syntax_job,
                str(build['upstream']),
                '/changes'
            )
            message = (
                'All tests triggered by upstream build #' +
                str(build['upstream']) +
                ' passed: ' +
                syntax_url +
                assignees(build['title'])
            )
            slack(user.slack_name, message)
        # Success notification for builds not in the core pipeline:
        if ('Core' not in build['build'] and
            user.notify_on_failure and
            user.notify_on_finish and
            build['result'] == 'SUCCESS'):
            message = (
                build['build'] +
                ' passed: ' +
                build['url'] +
                assignees(build['title'])
            )
            slack(user.slack_name, message)
        # Notifications for unusual build statuses (ABORTED, UNSTABLE, etc.):
        if (user.notify_on_failure and
            user.notify_on_finish and
            build['result'] and
            build['result'] != 'SUCCESS' and
            build['result'] != 'FAILURE'):
            message = (
                build['build'] +
                ' was ' +
                build['result'] +
                ': ' +
                build['url'] +
                assignees(build['title'])
            )
            slack(user.slack_name, message)
    # Add this build to the list of builds already handled:
    if build['result']:
        track_notifications.track(
            build['number'],
            build['timestamp'],
            'build_numbers'
        )

def slack(user, message):
    params = {
        'token': os.environ['BUILD_BOT_API_TOKEN'],
        'channel': '#build-notifications',
        'text': '@{}: {}'.format(user, message),
        'link_names': 1,
        'as_user': True
    }
    requests.get('https://slack.com/api/chat.postMessage', params=params)

def main():
    global HOSTNAME, JENKINS, MAX_AGE
    global current_time, passed_notifications
    passed_notifications = []
    # Convert time to milliseconds for comparison to Jenkins timestamp:
    current_time = time.time() * 1000
    JENKINS.auth = ('sneagle', os.environ['JENKINS_API_TOKEN'])
    JENKINS.timeout = 3
    JENKINS.proxies = {'http': os.environ['PROXIMO_URL']}
    jenkins_api = '/api/json?tree=jobs['\
        'builds['\
            'actions['\
                'causes['\
                    'shortDescription'\
                ']'\
            '],'\
            'number,'\
            'timestamp,'\
            'result,'\
            'url,'\
            'changeSet['\
                'items['\
                    'msg,'\
                    'author['\
                        'fullName,'\
                        'absoluteUrl'\
                    ']'\
                ']{0}'\
            '],'\
            'fullDisplayName'\
        ']'\
    ']'
    url = '{}{}'.format(HOSTNAME, jenkins_api)
    builds = parse_build_data(JENKINS.get(url).json())
    for build in builds:
        if (build and
            current_time - build['timestamp'] < MAX_AGE and 
            build['branch'] != 'master' and not 
            track_notifications.already_notified(
                build['number'],
                'build_numbers'
            )):
            notify(build, builds)
    track_notifications.clean(current_time, MAX_AGE, 'build_numbers')

if __name__ == '__main__':
    main()
