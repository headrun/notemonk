from django.core.management.base import BaseCommand
from core.models import *

class Command(BaseCommand):
    help = 'Process who are toppers and update in Toppers table for quick retrieval.'
    args = ''

    def handle(self, *args, **options):
    
        user_profiles = UserProfile.objects.filter(user__is_staff=False).order_by('-points')[:20]
        Toppers.objects.all().delete()

        for user_profile in user_profiles:
            Toppers.objects.create(user_profile = user_profile)

    def usage(self, subcommand):
        return ''
