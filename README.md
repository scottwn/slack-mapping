#slack-mapping
Originally written for the engineering team at Teachers Pay Teachers, `slack-mapping` is a Heroku app that notifies agile engineers via Slack when Jenkins builds complete or fail or when members of the team commit to GitHub or comment on selected repos. Engineers can interact wih the Slack bot, configurating notification preferences via Slack messages.
`clock.py` configures a Heroku cron job to check pull Jenkins and GitHub data and report new build statuses, commits, and comments.
`make_mapping.py` should be configured to run once a day or once a week or whatever's appropriate for your team to create mappings between GitHub, Jenkins, and Slack users.
`rtm.py` is the SlackClient listener for the Slack Real Time Messaging API. Good info about SlackClient is on their repo: https://github.com/slackapi/python-slackclient
