import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'www.settings'

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
