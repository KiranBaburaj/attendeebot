import os
import ssl  # Add this import
from redis import ConnectionPool

from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', ]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "attendee_development",
        "USER": "postgres",
        "PASSWORD": "916916",
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": "5432",
    }
}

INSTALLED_APPS = [
    'accounts',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'bots',
    'allauth',
    'allauth.account', 
        'allauth.socialaccount', # Add this line
    # ... other apps
]

# Log more stuff in development
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
DISABLE_REDIS_SSL = os.getenv('DISABLE_REDIS_SSL', 'True').lower() == 'true'

REDIS_CONNECTION_PARAMS = {
    'connection_pool': ConnectionPool.from_url(REDIS_URL),
    'ssl': False,
    'ssl_cert_reqs': None
}
if not DISABLE_REDIS_SSL:
    REDIS_CONNECTION_PARAMS.update({
        'ssl': True,
        'ssl_cert_reqs': ssl.CERT_NONE
    })
