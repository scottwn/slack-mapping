import yaml
import csv
import push_to_github
import users_to_yaml
from base64 import b64encode

def user_is_already_mapped(user, csvfile):
    mapping = csv.DictReader(csvfile, lineterminator='\n')
    for mapped_user in mapping:
        if user in mapped_user.values():
            return True
    return False

def make_new_user(user, slack_mapping):
    return {
        'real_name': slack_mapping[user]['real_name'],
        'slack_name': user,
        'slack_id': slack_mapping[user]['id'],
        'email': slack_mapping[user]['email'],
        'notify_on_finish': False,
        'notify_on_failure': False
    }

def get_new_users(csvfile, slack_mapping):
    new_users = []
    for user in slack_mapping:
        csvfile.seek(0, 0)
        if not user_is_already_mapped(user, csvfile):
            new_users.append(make_new_user(user, slack_mapping))
    return new_users
 
def main():
    # Call script to pull list of users from Slack API and write to YAML:
    users_to_yaml.main()
    slack_mapping = yaml.safe_load(open('user_mapping.yaml', 'r'))
    # Get a list of users who aren't in mapping.csv:
    with open('mapping.csv', 'r', newline='') as csvfile:
        new_users = get_new_users(csvfile, slack_mapping)
    # Append the new users to mapping.csv:
    with open('mapping.csv', 'a', newline='') as csvfile:
        fieldnames = [
            'real_name', 
            'slack_name',
            'slack_id', 
            'email', 
            'notify_on_finish',
            'notify_on_failure'
        ]
        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames,
            lineterminator='\n'
        )
        for user in new_users:
            writer.writerow(user)
    push_to_github.main('mapping.csv', 'Updated mapping.')

if __name__ == '__main__':
    main()
