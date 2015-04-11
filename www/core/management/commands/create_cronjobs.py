from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_noop as _
from chronograph.models import Job

class Command(BaseCommand):
    help = 'Creates cronjobs in chronograph. Run once at installation time.'
    args = ''

    def handle(self, *args, **options):
        cron = lambda **kwargs: Job.objects.create(**kwargs)

        cron(name='Send Mails', frequency='MINUTELY', params='interval:1', command='send_mail', args='', disabled=False)
        cron(name='Process Ratings', frequency='MINUTELY', params='interval:1', command='process_ratings', args='', disabled=False)
        cron(name='Process Toppers', frequency='HOURLY', params='interval:1', command='process_toppers', args='', disabled=False)
        cron(name='Process Onliners', frequency='HOURLY', params='interval:1', command='process_onliners', args='', disabled=False)
        cron(name='Emit Notices', frequency='MINUTELY', params='interval:1', command='emit_notices', args='', disabled=False)
        cron(name='Update Leaderboard Data', frequency='HOURLY', params='interval:2', command='update_leaderboarddata', args='', disabled=False)

    def usage(self, subcommand):
        return ''
