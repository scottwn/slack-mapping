import yaml
import csv
import re
import os
import push_to_github
from slackclient import SlackClient

#global constants
SC = SlackClient(os.environ['BUILD_BOT_API_TOKEN'])

def subscribe(channel, user, command):
    global SC
    filename = command + '_subscriptions.yaml'
    channel_subscriptions = yaml.safe_load(open(filename, 'r'))
    # If this channel is already subscribed to some users, append the user, 
    # otherwise create a new dict entry:
    print('channel = ' + channel)
    print('user = ' + user)
    print(filename + ' = ')
    print(str(channel_subscriptions))
    if (channel in channel_subscriptions and
        user not in channel_subscriptions[channel]):
        channel_subscriptions[channel].append(user)
    elif channel not in channel_subscriptions:
        channel_subscriptions[channel] = [user]
    else:
        message = (
            "This channel is already subscribed to <@" +
            user +
            ">'s " +
            command +
            "s."
        )
        SC.rtm_send_message(channel, message)
    with open(filename, 'w') as outfile:
        yaml.dump(channel_subscriptions, outfile, width=1000)
    push_to_github.main(filename, 'Updated ' + command + ' subscriptions.')

def unsubscribe(channel, user, command):
    global SC
    message = ''
    filename = command + '_subscriptions.yaml'
    channel_subscriptions = yaml.safe_load(open(filename, 'r'))
    # If this channel is subscribed to this user, remove the user, otherwise 
    # send a message:
    if (channel in channel_subscriptions and
        user in channel_subscriptions[channel]):
        channel_subscriptions[channel].remove(user)
    elif channel not in channel_subscriptions:
        message = "No one is subscribed in this channel."
    else:
        message = (
            "I wasn't sending notifications for <@" +
            user +
            ">'s " +
            command +
            "s, but ok..."
        )
    if message:
        SC.rtm_send_message(channel, message)
    with open(filename, 'w') as outfile:
        yaml.dump(channel_subscriptions, outfile, width=1000)
    push_to_github.main(filename, 'Updated ' + command + ' subscriptions.')

def update_mapping(notification, user, is_off):
    new_mapping = []
    with open('mapping.csv', 'r', newline='') as csvfile:
        mapping = csv.DictReader(csvfile, lineterminator='\n')
        for row in mapping:
            new_mapping.append(row)
    for row in new_mapping:
        if user in row.values():
            row[notification] = not is_off
    with open('mapping.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(
            csvfile,
            new_mapping[0].keys(),
            lineterminator='\n'
        )
        writer.writeheader()
        writer.writerows(new_mapping)
    push_to_github.main('mapping.csv', 'Updated mapping.')
    if is_off:
        on_or_off = "won't"
    else:
        on_or_off = "will"
    return (
        '<@' +
        user +
        '> I ' +
        on_or_off +
        ' let you know in #build-notifications when your Jenkins builds '
    )

# This bot has mandatory fun!
def random_response():
    r = int.from_bytes(os.urandom(1), byteorder='big')
    if r < 125:
        return ':metal:'
    return 'HELLO I AM ROBOT BEEP BOOP'

def get_command(text):
    if 'comment' in text:
        return ['comment', 'comments on a pull request.']
    if 'pull' in text or 'PR' in text:
        return ['pull', 'opens a pull request.']
    return ['commit', 'commits to master.']

def process(message):
    global SC
    outgoing_message = ''
    # Get everything in the message after the mention of @build_notifications:
    try:
        you_said = message['text'].split(' ', 1)[1]
    except IndexError:
        you_said = ''
        SC.rtm_send_message(message['channel'], ':confounded:')
    # Regex to parse user IDs from message:
    users = re.findall('(?<=@)\w+(?=>)', you_said)
    command = get_command(you_said)
    if 'unsubscribe' in you_said:
        for user in users:
            unsubscribe(message['channel'], user, command[0])
        stop_or_start = "I'll stop notifying this channel when <@"
    elif 'subscribe' in you_said:
        for user in users:
            subscribe(message['channel'], user, command[0])
        stop_or_start = "OK, I'll notify this channel when <@"
    elif 'failure' in you_said:
        outgoing_message = update_mapping(
            'notify_on_failure',
            message['user'],
            'off' in you_said
        )
        outgoing_message += 'fail.'
    elif 'finish' in you_said:
        outgoing_message = update_mapping(
            'notify_on_finish',
            message['user'],
            'off' in you_said
        )
        outgoing_message += 'pass.'
    elif 'help' in you_said:
        outgoing_message = (
            'Help can be found on the wiki! ' +
            'https://teacherspayteachers.atlassian.net/' +
            'wiki/' +
            'display/' +
            'ENGINEERING/' +
            'Build+Bot'
        )
    else:
        outgoing_message = random_response()
    if not outgoing_message and len(users) == 1:
        outgoing_message = stop_or_start + users[0] + '> ' + command[1]
    if not outgoing_message and len(users) > 1:
        users_message = ''
        for i in range(0, len(users) - 1):
            users_message += (users[i] + '>, <@')
        users_message += ('> and <@' + users[len(users) - 1] + '> ')
        outgoing_message = stop_or_start + users_message + command[1]
    if outgoing_message:
        SC.rtm_send_message(message['channel'], outgoing_message)
    else:
        SC.rtm_send_message(message['channel'], ':confounded:')

def get_messages(messages):
    build_bot_mention_string = '<@U1R49SZNK>'
    for message in messages:
        # Check if the message mentions @build_notifications:
        if ('text' in message and
            build_bot_mention_string in message['text']):
            process(message)

def main():
    global SC
    if SC.rtm_connect():
        while True:
            get_messages(SC.rtm_read())
    else:
        print('Connection failed.')

if __name__ == '__main__':
    main()
