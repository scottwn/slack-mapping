import jenkins_slack_notifications
import github_slack_notifications
from apscheduler.schedulers.blocking import BlockingScheduler

def jenkins():
    jenkins_slack_notifications.main()

def github():
    github_slack_notifications.main()

if __name__ == '__main__':
    scheduler = BlockingScheduler()
    scheduler.add_job(jenkins, 'interval', seconds=10)
    scheduler.add_job(github, 'interval', seconds=60)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
