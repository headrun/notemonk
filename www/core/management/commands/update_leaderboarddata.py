import datetime
from itertools import groupby

from django.core.management.base import BaseCommand

from core.models import *

class Command(BaseCommand):
    help = "Load data into leaderboard table"
    args = ''

    def handle(self, *args, **options):

        ratings = Ratings.objects.order_by('-date_added')[:10000]
        users = [(r.user.id, r.user) for r in ratings]
        users.sort()
        users = [u for _id, u in users]
        users = [list(g) for key, g in groupby(users, lambda u: u.id)]
        users = [(len(g), g) for g in users]
        users.sort()
        users.reverse()
        users = [u[0] for count, u in users]

        LeaderBoardData.objects.all().delete()
        for u in users:
            LeaderBoardData.objects.create(tag='active',
                target_type=u.get_profile().ctype,
                target_id=u.get_profile().id)

    def usage(self, subcommand):
        return ''
