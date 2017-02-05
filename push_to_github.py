import json
import os
import requests
from base64 import b64encode

def main(filename, commit_message):
    # Convert file to byte object:
    with open(filename, 'r', newline='') as infile:
        byte_encoded = infile.read().encode()
    # Base64 encoding for upload:
    updated_file = b64encode(byte_encoded)
    file_url = 'https://api.github.com/'\
        'repos/'\
        'TeachersPayTeachers/'\
        'slack-mapping/'\
        'contents/'
    file_url += filename
    token_header = 'token ' + os.environ['GITHUB_REPO_TOKEN']
    header = {'Authorization': token_header}
    file_sha = requests.get(file_url, headers=header).json()['sha']
    upload = {
        'message': commit_message,
        'sha': file_sha,
        'content': str(updated_file, 'utf-8')
    }
    requests.put(file_url, data=json.dumps(upload), headers=header)
