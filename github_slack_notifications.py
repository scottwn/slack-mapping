import yaml
import re
import json
import os
import requests
import datetime
import get_etags
import track_notifications
from base64 import b64decode
from get_slack_id import GetSlackID

# global constants:
MAX_AGE = 100 #seconds
GITHUB_API = 'https://api.github.com/repos/TeachersPayTeachers/'
TOKEN_HEADER = {'Authorization': 'token ' + os.environ['GITHUB_REPO_TOKEN']}

# global variables:
current_time = datetime.datetime(datetime.MINYEAR, 1, 1)
etags = {}

# Check the subscriptions file to see which Slack channels are subscribed to
# this user:
def notifications_on(command, user):
    global etags, GITHUB_API, TOKEN_HEADER
    filename = command + '_subscriptions.yaml'
    etag = ''
    if command in etags.keys():
        etag = '"' + re.findall('\w\w+', etags[command])[0] + '"'
    headers = {**TOKEN_HEADER, **{'If-None-Match': etag}}
    url = GITHUB_API + 'slack-mapping/contents/' + filename
    subscriptions = requests.get(url, headers=headers)
    etags[command] = subscriptions.headers['Etag']
    if subscriptions.status_code < 304:
        b64encoded = bytearray(subscriptions.json()['content'], 'utf-8')
        with open(filename, 'w') as outfile:
            outfile.write(b64decode(b64encoded).decode())
    channel_subscriptions = yaml.safe_load(open(filename, 'r'))
    notifications_on = []
    for channel in channel_subscriptions:
        if user in channel_subscriptions[channel]:
            notifications_on.append(channel)
    return notifications_on

# Send a message to a list of Slack channels:
def slack(message, channels):
    for channel in channels:
        params = {
            'token': os.environ['BUILD_BOT_API_TOKEN'],
            'channel': channel,
            'text': message,
            'as_user': True
        }
        requests.get('https://slack.com/api/chat.postMessage', params=params)

# Attempt to map data in a notification (commit, pull, or comment) to a Slack
# user:
def user_from_notification(notification):
    if notification:
        return GetSlackID(
            notification['author'],
            notification['email'],
            notification['user']
        )

# Superclass for notifications:
class Notify:

    def __init__(self):
        global TOKEN_HEADER, MAX_AGE, current_time
        timestamp_format = '%a, %d %b %Y %H:%M:%S GMT'
        max_age = datetime.timedelta(seconds=MAX_AGE)
        time_since = (current_time - max_age).strftime(timestamp_format)
        self.header = {**TOKEN_HEADER, **{'If-Modified-Since': time_since}}

    # Get JSON data from the Github API:
    def get_data(self):
        data = requests.get(self.url, headers=self.header)
        if data.status_code < 304:
            return data.json()
        else:
            return []

    # Process JSON data from the Github API:
    def set_data(self):
        timestamp_format = '%Y-%m-%dT%H:%M:%SZ'
        data = self.get_data()
        self.notifications = []
        for d in data:
            # Return a Python datetime object from a JSON timestamp:
            time = datetime.datetime.strptime(self.get_time(d), timestamp_format)
            self.notifications.append(self.new_notification(d, time))
            self.user_data = {}
            track_notifications.track(
                self.get_number(d),
                # Unix time in milliseconds for track_notifications:
                time.timestamp() * 1000,
                self.filename
            )

    def new_notification(self, data, time):
        global MAX_AGE, current_time
        # If a commit, pull, or comment isn't too old and we haven't already
        # sent a Slack message for it, return data necessary to create a
        # notification:
        if ((current_time - time).total_seconds() < MAX_AGE and not
            track_notifications.already_notified(
                self.get_number(data),
                self.filename
            )):
            return {
                'author': self.get_author(data),
                'email': self.get_email(data),
                'user': self.get_user(data),
                'url': data['html_url'],
                'body': self.get_body(data)
            }

    # This is an abstract method. It's implemented in the Comments class to return
    # the body of a comment.
    def get_body(self, data):
        pass

    def send_notifications(self):
        for notification in self.notifications:
            user = user_from_notification(notification)
            self.notification_for_user(notification, user)

    def notification_for_user(self, notification, user):
        if user and user.exists:
            channels = self.get_channels(user.slack_id)
            message = self.get_message(notification)
            slack(message, channels)

class Commits(Notify):

    def __init__(self):
        global GITHUB_API
        super().__init__()
        self.url = GITHUB_API + 'tpt/commits'
        self.filename = 'shas'

    def get_time(self, commit):
        return commit['commit']['author']['date']

    def get_number(self, commit):
        return commit['sha']

    def get_author(self, commit):
        return commit['commit']['author']['name']

    def get_email(self, commit):
        return commit['commit']['author']['email']

    def get_user(self, commit):
        return commit['author']['login']

    def get_channels(self, user):
        return notifications_on('commit', user)

    def get_message(self, commit):
        return (
            commit['author'] +
            ' committed to master: ' +
            commit['url']
        )

class Pulls(Notify):

    def __init__(self):
        super().__init__()
        self.filename = 'pull_numbers'
        self.user_data = {}

    def get_url(self, repo):
        global GITHUB_API
        return GITHUB_API + repo + '/pulls'

    def get_new_repo(self, url, headers):
        data = requests.get(url, headers=headers)
        if data.status_code < 304:
            return (data.json(), data.headers['Etag'])
        else:
            return ([], '')

    def add_etag(self, etag, repo):
        global etags
        if etag:
            etags[repo] = etag

    def get_headers(self, repo):
        global etags
        if repo in etags.keys():
            # Format the etag header for GitHub API:
            etag = '"' + re.findall('\w\w+', etags[repo])[0] + '"'
            return {**self.header, **{'If-None-Match': etag}}
        return self.header

    def get_etag(self, repo):
        return repo + '-pulls'

    def get_data(self):
        repos_url = 'https://api.github.com/orgs/TeachersPayTeachers/repos'
        repos = self.get_repos(repos_url)
        data = []
        for repo in repos:
            url = self.get_url(repo['name'])
            etag_name = self.get_etag(repo['name'])
            headers = self.get_headers(etag_name)
            #get_new_repo returns a tuple of the form (list_of_pulls, Etag)
            new_repo = self.get_new_repo(url, headers)
            data += new_repo[0]
            self.add_etag(new_repo[1], etag_name)
        return data

    def get_repos(self, repos_url):
        global TOKEN_HEADER
        tpt_repos = requests.get(repos_url, headers=TOKEN_HEADER)
        # If there are more pages of repos, get them recursively:
        headers = tpt_repos.headers
        if 'link' in headers.keys() and 'next' in headers['link']:
            # Regex to parse URL from header:
            url = re.findall('(?<=<)\S+(?=>)', headers['link'])[0]
            return tpt_repos.json() + self.get_repos(url)
        return tpt_repos.json()

    def get_time(self, pull):
        return pull['created_at']

    def get_number(self, pull):
        return pull['id']

    def get_author(self, pull):
        self.check_user_data(pull)
        return self.user_data['name']

    def get_email(self, pull):
        self.check_user_data(pull)
        return self.user_data['email']

    def get_user(self, pull):
        return pull['user']['login']

    # If user_data is empty, call the GitHub users API:
    def check_user_data(self, pull):
        global TOKEN_HEADER
        if not self.user_data:
            user_url = 'https://api.github.com/users/' + pull['user']['login']
            self.user_data = requests.get(
                user_url,
                headers=TOKEN_HEADER
            ).json()

    def get_channels(self, user):
        return notifications_on('pull', user)

    def get_message(self, pull):
        return (
            pull['author'] +
            ' opened a pull request: ' +
            pull['url']
        )

# Comments is a subclass of Pulls because these API responses are structured in
# a very similar way.
class Comments(Pulls):

    def __init__(self):
        super().__init__()
        self.filename = 'comment_ids'

    def get_url(self, repo):
        global GITHUB_API
        url = GITHUB_API + repo + '/issues/comments'
        etag_name = self.get_etag(repo)
        headers = self.get_headers(etag_name)
        # The newest comments are on the last page of comments. The link to the
        # last page of comments is returned in the header of the API response.
        response = requests.get(url, headers=headers)
        # Regex to parse URL from header:
        if 'link' in response.headers.keys():
            return re.findall('(?<=<)\S+(?=>)', response.headers['link'])[1]
        return url

    def get_etag(self, repo):
        return repo + '-comments'

    def get_body(self, comment):
        return comment['body']

    def get_channels(self, user):
        return notifications_on('comment', user)

    def get_message(self, comment):
        return (
            comment['author'] +
            ' made a comment: ```' +
            comment['body'] +
            '``` ' +
            comment['url']
        )

def main():
    global current_time, etags, MAX_AGE
    etags = get_etags.main()
    # Python datetime object representing current time in UTC:
    current_time = datetime.datetime.utcnow()
    notifications = [Commits(), Pulls(), Comments()]
    for notification in notifications:
        notification.set_data()
        notification.send_notifications()
        track_notifications.clean(
            # Unix time in milliseconds for track_notifications:
            current_time.timestamp() * 1000,
            # Convert seconds to milliseconds for track_notifications:
            MAX_AGE * 1000,
            notification.filename
        )
    with open('etags', 'w') as outfile:
        json.dump(etags, outfile)

if __name__ == '__main__':
    main()
