# Stub settings for school-base

DEBUG = TEMPLATE_DEBUG = True
MANAGERS = ADMINS = []
DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = 'db.sqlite3'
TIME_ZONE = 'UTC'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = False
MEDIA_ROOT = 'docroot/static/'
MEDIA_URL = '/static/'
ADMIN_MEDIA_PREFIX = '/media/'
SECRET_KEY = 'notverysecret'
ROOT_URLCONF = 'urls'
TEMPLATE_DIRS = []

TEMPLATE_LOADERS = (
    'django.template.loaders.app_directories.load_template_source',
    'django.template.loaders.filesystem.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
)

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'infobase',
    'equipment'
)
