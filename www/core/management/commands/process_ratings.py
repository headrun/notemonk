from django.core.management.base import BaseCommand
from core.models import *
from core.points import give_points

MAX_NOTIFICATIONS = 1000

class Command(BaseCommand):
    help = 'Process Rating Notifications and award User Points.'
    args = ''

    def handle(self, *args, **options):
        rns = RatingNotification.objects.all()[:MAX_NOTIFICATIONS]

        for rn in rns:
            give_points('rated', target=rn.target, num_ratings=rn.num_ratings)
            rn.delete()

    def usage(self, subcommand):
        return ''
