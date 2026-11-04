"""
Django settings for backend project.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('Falta SECRET_KEY en el archivo .env')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False').strip().lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,10.0.2.2').split(',')
    if h.strip()
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Aplicación del proyecto
    'api',
    'rest_framework',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


WSGI_APPLICATION = 'wsgi.application'
ASGI_APPLICATION = 'asgi.application'


# Database

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('HIST_DB_NAME'),
        'USER': os.getenv('HIST_DB_USER'),
        'PASSWORD': os.getenv('HIST_DB_PASSWORD'),
        'HOST': os.getenv('HIST_DB_HOST'),
        'PORT': os.getenv('HIST_DB_PORT'),
    },

    'tiempo_real': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('TR_DB_NAME'),
        'USER': os.getenv('TR_DB_USER'),
        'PASSWORD': os.getenv('TR_DB_PASSWORD'),
        'HOST': os.getenv('TR_DB_HOST'),
        'PORT': os.getenv('TR_DB_PORT'),
        'OPTIONS': {'options': '-c search_path=convencionales,public'},
    },

    'pronostico': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('PR_DB_NAME'),
        'USER': os.getenv('PR_DB_USER'),
        'PASSWORD': os.getenv('PR_DB_PASSWORD'),
        'HOST': os.getenv('PR_DB_HOST'),
        'PORT': os.getenv('PR_DB_PORT'),
        'OPTIONS': {
            'options': '-c search_path=alerta_incendios,public',
        },
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATABASE_ROUTERS = ['db_routers.DatabaseRouter']

AUTH_USER_MODEL = 'api.Usuario'
MIGRATION_MODULES = {'api': None}


# Django REST Framework

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
    # No escribir last_login: seguridades.usuarios es compartida con otros sistemas.
    'UPDATE_LAST_LOGIN': False,
}

AUTHENTICATION_BACKENDS = ['api.autenticacion.Sha256Backend']


# Internationalization

LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/Guayaquil'

USE_I18N = True

USE_TZ = True


# Static files

STATIC_URL = 'static/'


# Email (en desarrollo imprime los correos en la consola)

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'