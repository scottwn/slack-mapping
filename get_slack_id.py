import csv
import os
import requests
import json
import re
import get_etags
from base64 import b64decode

def check_match(match, mapping):
    for user in mapping:
        if match in user.values():
            return user

def user_in_mapping(csvfile, matches):
    mapping = csv.DictReader(csvfile, lineterminator='\n')
    output = {}
    for match in matches:
        csvfile.seek(0,0)
        output = check_match(match, mapping)
        if match and output:
            return output

def string_to_bool(string):
    if string == 'True':
        return True

def update_mapping(downloaded_data):
    with open('mapping.csv', 'w', newline='') as csvfile:
        csvfile.write(b64decode(bytearray(downloaded_data, 'utf-8')).decode())

class GetSlackID:

    def __init__(self, author, email, user):
        self.exists = False
        matches = [user, email, author]
        ignored_users = ['noreply', 'tptdeploybot', 'Darkseid-Apokolips']
        etag = ''
        etags = get_etags.main()
        if 'mapping' in etags.keys():
            etag = '"' + re.findall('\w\w+', etags['mapping'])[0] + '"'
        token_header = 'token ' + os.environ['GITHUB_REPO_TOKEN']
        headers = {'Authorization': token_header, 'If-None-Match': etag}
        mapping_url = 'https://api.github.com/'\
            'repos/'\
            'TeachersPayTeachers/'\
            'slack-mapping/'\
            'contents/'\
            'mapping.csv'
        mapping = requests.get(mapping_url, headers=headers)
        etags['mapping'] = mapping.headers['Etag']
        with open('etags', 'w') as outfile:
            json.dump(etags, outfile)
        if mapping.status_code < 304:
            update_mapping(mapping.json()['content'])
        with open('mapping.csv', 'r', newline='') as csvfile:
            output = user_in_mapping(csvfile, matches)
        if output:
            self.slack_id = output['slack_id']
            self.slack_name = output['slack_name']
            self.notify_on_failure = string_to_bool(output['notify_on_failure'])
            self.notify_on_finish = string_to_bool(output['notify_on_finish'])
            self.exists = True
        elif author and user and user not in ignored_users:
            print(
                author +
                ' (' +
                user +
                ') is an unknown user. Add this user to mapping.csv.'
            )
