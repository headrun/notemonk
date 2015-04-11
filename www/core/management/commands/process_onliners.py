import datetime
from django.core.management.base import BaseCommand
from core.models import *

class Command(BaseCommand):
    help = 'Find who are online in last one hour and update in Onliners Table.'
    args = ''

    def handle(self, *args, **options):
        one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=5)
        sql_datetime = datetime.datetime.strftime(one_hour_ago, '%Y-%m-%d %H:%M:%S')
        online_users = User.objects.filter(last_login__gt=sql_datetime,
                                is_active__exact=1).order_by('-last_login')[:10]
    
        Onliners.objects.all().delete()

        for onliner in online_users:
            Onliners.objects.create(user = onliner)

    def usage(self, subcommand):
        return ''
