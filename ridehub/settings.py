import os
from pathlib import Path

import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY_FOR_DEVELOPMENT = 'not-so-secret-default-for-development'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', SECRET_KEY_FOR_DEVELOPMENT)

IS_HEROKU_APP = "DYNO" in os.environ and "CI" not in os.environ

WEB_HOST = os.environ.get('WEB_HOST', 'obcrides.ca')

if IS_HEROKU_APP:
    ALLOWED_HOSTS = ["*"]
    SECURE_SSL_REDIRECT = True
    DEBUG = False
    assert SECRET_KEY != SECRET_KEY_FOR_DEVELOPMENT
else:
    ALLOWED_HOSTS = [".localhost", "127.0.0.1", "[::1]", "0.0.0.0", "[::]"]
    DEBUG = True

INSTALLED_APPS = [
    'whitenoise.runserver_nostatic',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_cotton',
    'django_celery_beat',
    'phonenumber_field',
    'waffle',
    'behave_django',
    'django_gravatar',
    'django_prose_editor',
    'adminsortable2',
    'backoffice',
    'web',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'waffle.middleware.WaffleMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'sesame.backends.ModelBackend',
]

SESAME_MAX_AGE = 60 * 5
SESAME_ONE_TIME = os.environ.get('SESAME_ONE_TIME') is not None

LOGIN_REDIRECT_URL = "/profile"
LOGIN_URL = "/login/"

if IS_HEROKU_APP:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', None)
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', None)
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', None)
    EMAIL_FROM = os.environ.get('EMAIL_FROM', None)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    EMAIL_FROM = 'noreply@noreply'

ROOT_URLCONF = 'ridehub.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'web.context_processors.version_info',
            ],
        },
    },
]

WSGI_APPLICATION = 'ridehub.wsgi.application'

if IS_HEROKU_APP:
    DATABASES = {
        "default": dj_database_url.config(
            env="DATABASE_URL",
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        ),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Toronto'

USE_I18N = True

USE_TZ = True

STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SENTRY_DSN = os.environ.get('SENTRY_DSN', None)

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=os.environ.get('SENTRY_DSN', SENTRY_DSN),
        send_default_pii=True,
        traces_sample_rate=1.0,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        release=os.environ.get('HEROKU_RELEASE_VERSION', 'unknown'),
        _experiments={
            'enable_logs': True,
        }
    )

# Celery Configuration
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
CELERY_WORKER_TASK_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'