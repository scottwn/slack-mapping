# Script to get list of users from Slack API and write to YAML:
import os
import json
import requests
from yaml import dump

def get_member_data(members):
    member_data = []
    for member in members:
        if not member.get('is_bot') and not member.get('is_restricted'):
            member_concise = {
                'id': member['id'],
                'name': member['name'],
                'email': member['profile']['email'],
                'real_name': member['profile']['real_name']
            }
            member_data.append(member_concise)
    return member_data

def get_members_from_api():
    url='https://slack.com/api/users.list'
    token = os.environ['BUILD_BOT_API_TOKEN']
    return requests.get(url, params={'token': token}).json()['members']

def main():
    members = get_members_from_api()
    member_data = get_member_data(members)
    to_yaml = {}
    for member in member_data:
        to_yaml[str(member['name'])] = {
            'id': str(member['id']),
            'email': str(member['email']),
            'real_name': str(member['real_name'])
        }
    with open('user_mapping.yaml', 'w') as outfile:
        dump(to_yaml, outfile, width=1000)

if __name__ == '__main__':
    main()
