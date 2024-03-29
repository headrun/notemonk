import os
import logging

def create_logger(filename, log_level=logging.NOTSET, stderr=False):
    '''
    Make a logger that writes to I{filename}.

    @type filename: str
    @param filename: filename of file to which log has to be written

    @type log_level: logging.<log level>
    @param log_level: logging.[DEBUG, INFO, EXCEPTION, WARNING]

    @return: log object
    '''

    logger = logging.getLogger()
    handler = logging.FileHandler(filename)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if stderr:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(log_level)

    return logger


LOG_FNAME = 'notemonk.log'
create_logger(LOG_FNAME, logging.DEBUG)

DEBUG = True
TEMPLATE_DEBUG = DEBUG

PROJNAME = os.path.basename(os.path.dirname(__file__))

ADMINS = (
    ('Notemonk', 'monk@notemonk.com'),
)

MANAGERS = ADMINS

#DATABASE_ENGINE = 'sqlite3'     # or 'oracle', 'postgresql_psycopg2', 'postgresql', 'mysql',
#DATABASE_NAME = 'sitebase.db'   # Or path to database file if using sqlite3.
#DATABASE_USER = ''             # Not used with sqlite3.
#DATABASE_PASSWORD = ''         # Not used with sqlite3.
#DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
#DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

DATABASE_ENGINE = 'mysql'     # or 'oracle', 'postgresql_psycopg2', 'postgresql', 'mysql',
DATABASE_NAME = 'notemonk_db'   # Or path to database file if using sqlite3.
DATABASE_USER = 'root'             # Not used with sqlite3.
DATABASE_PASSWORD = 'datameter273'         # Not used with sqlite3.
DATABASE_HOST = 'localhost'             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'
SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'static')

STATICFILES_DIRS = [MEDIA_ROOT]
STATIC_URL = '/static/'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = 'http://static.notemonk.com/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'
ADMIN_MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'media')

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'ny2a@_*z4^9nw93nd96hdte*e#&x!**rskn(*k0h99y+u^-y3g'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'johnny.middleware.LocalStoreClearMiddleware',
    'johnny.middleware.QueryCacheMiddleware',
    'django.middleware.cache.UpdateCacheMiddleware',
    'core.utils.StripCookieMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'facebook.djangofb.FacebookMiddleware',
    'core.recaptcha_form.RecaptchaMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
    'core.debug.SqlPrintingMiddleware',
)

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'core.auth_backends.FacebookBackend',
    )

# Context Processors
TEMPLATE_CONTEXT_PROCESSORS = [
   'django.core.context_processors.auth',
   'django.core.context_processors.media',
   'django.core.context_processors.request',
]

if DEBUG:
    TEMPLATE_CONTEXT_PROCESSORS.append(
       'django.core.context_processors.debug')

ROOT_URLCONF = '%s.urls' % PROJNAME

TEMPLATE_DIRS = (
    os.path.join(os.path.dirname(__file__), 'templates').replace('\\', '/'),
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

APPEND_SLASH = True

INTERNAL_IPS = ('127.0.0.1')
#INTERNAL_IPS = ('127.0.0.1', '115.252.180.228')

def custom_show_toolbar(request):
    remote_ip = request.META.get('REMOTE_ADDR', None)
    return remote_ip in INTERNAL_IPS

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': custom_show_toolbar,
    'INTERCEPT_REDIRECTS': False,
}

CACHE_BACKEND = 'memcached://127.0.0.1:11211/'
JOHNNY_CACHE_BACKEND = CACHE_BACKEND
JOHNNY_MIDDLEWARE_KEY_PREFIX='jc_myproj'

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.admindocs',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.comments',
    'django.contrib.staticfiles',
    'reversion',
    'registration',
    'markitup',
    'mailer',
    'notification',
    'south',
    'chronograph',
    'debug_toolbar',
    '%s.core' % PROJNAME,
)

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/login/done/'

AUTH_PROFILE_MODULE = 'core.UserProfile'

FACEBOOK_API_KEY = '7703fdc51bb3335309922341cdb1ec0f'
FACEBOOK_SECRET_KEY = 'de54204098ee835ead92494d532c8454'

GOOGLE_API_KEY = 'ABQIAAAABXgfV0AIiD-Sh91u8PWF1hTcWMrQi-gXWhUrBy2z8tO26jF3ChS6N36bzQ7AzAxGftdDJ-XQZDQBtg'
MARKITUP_FILTER = ('markdown.markdown', {'safe_mode': True, 'extensions':['urlize', 'safeimage']})
MARKITUP_SET = 'markitup/sets/markdown'
MARKITUP_SKIN = 'markitup/skins/simple'

ACCOUNT_ACTIVATION_DAYS = 7

DEFAULT_FROM_EMAIL = 'mailer5@notemonk.com'

RECAPTCHA_PRIVATE_KEY = '6LdvuQsAAAAAAMZEvIaakrNRtEkhfNzHOq7VvPf2'
RECAPTCHA_PUBLIC_KEY = '6LdvuQsAAAAAAChoAZ98QOiJGOLUrvKsJ9JNU8Kr'

CACHE_DIR = '/var/www/notemonk.com/www/cache/'
OPENID_SREG = {"requred": "nickname, email", "optional":"postcode, country", "policy_url": ""}
OPENID_AX = [{"type_uri": "email",
             "count": 1,
             "required": True,
             "alias": "email"},
            {"type_uri": "fullname",
             "count":1 ,
             "required": False,
             "alias": "fullname"}]

OPENID_REDIRECT_NEXT = '/accounts/openid/done/'

NOTIFICATION_QUEUE_ALL = False
SUPERUSERS_NOTIFY = True

SEND_BROKEN_LINK_EMAILS = True
SERVER_EMAIL = 'monk@notemonk.com'

EMAIL_BACKEND = 'core.utils.RoundRobinEmailBackend'
RR_EMAIL_USERS = [x + '@notemonk.com' for x in ('monk', 'admin', 'mailer1', 'mailer2', 'mailer3', 'mailer4', 'mailer5')]

EMAIL_USE_TLS = True
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'monk@notemonk.com'
EMAIL_HOST_PASSWORD = 'Willy45Nilly!'
EMAIL_PORT = 587

FILE_UPLOAD_PERMISSIONS = 0644

#if DEBUG:
#    EMAIL_HOST = '127.0.0.1'
#    EMAIL_PORT = 1025

CACHE_MIDDLEWARE_ANONYMOUS_ONLY = True
#CACHE_MIDDLEWARE_ALIAS = 'default'
#CACHE_MIDDLEWARE_SECONDS = 600
#CACHE_MIDDLEWARE_KEY_PREFIX = ''
