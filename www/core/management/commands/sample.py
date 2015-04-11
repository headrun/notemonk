from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "command name is 'sample'"
    args = ''

    def handle(self, *args, **options):
        from django.conf import settings
        pass

    def usage(self, subcommand):
        return ''
