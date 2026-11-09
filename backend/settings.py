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
    'drf_spectacular',
    'corsheaders',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
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
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# Sitios desde los que el navegador puede llamar a esta API (el visor web)
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv('CORS_ALLOWED_ORIGINS', 'https://inamhi.gob.ec,http://localhost:4200').split(',') if o.strip()
]

# Servidor de contenidos donde se guardan las fotos de los reportes
CONTENTX_URL_UPLOAD = os.getenv('CONTENTX_URL_UPLOAD', '')
CONTENTX_TOKEN = os.getenv('CONTENTX_TOKEN', '')

# Swagger / OpenAPI: /api_incendios/docs/ (Swagger), /redoc/ y /schema/
SPECTACULAR_SETTINGS = {
    'TITLE': 'API Alertas de Incendios - INAMHI',
    'VERSION': '1.0.0',
    'DESCRIPTION': """
API del sistema de alertas de incendios forestales.

**URL base:** `https://apis.inamhi.gob.ec/api_incendios/`

## Cómo autenticarse
1. `POST login/` con `{"username": "...", "password": "..."}` → devuelve `access`, `refresh` y `usuario`.
2. En cada endpoint protegido envía el header `Authorization: Bearer <access>`.
3. El `access` dura **30 minutos**. Si un endpoint responde 401, llama a `POST token/refresh/`
   con `{"refresh": "..."}` para obtener uno nuevo. El `refresh` dura **7 días**; si también vence, vuelve al login.
4. Al cerrar sesión basta con borrar `access` y `refresh` del front.

Para probar aquí: usa *login*, copia el `access` y pégalo en el botón **Authorize** (solo el token, sin "Bearer").

## Grupos y permisos
| id | grupo | acceso |
|---|---|---|
| 1 | aplicacion incendios guardaparques | reportar (se valida solo) y validar reportes de sus áreas |
| 2 | aplicacion incendios brigadas | aledaños: reportar (espera validación) |

Sin login se puede consultar todo lo público, incluidas las alertas, pero no reportar.

- El token incluye los claims `first_name` y `grupos` (lista de ids) para pintar la interfaz rápido.
- Al abrir la app conviene llamar a `GET me/`: devuelve los grupos actuales leídos de la base.
- Lo que el front muestre u oculte es solo visual: el backend valida el grupo en cada petición.

## Códigos de respuesta
| código | significado |
|---|---|
| 200 | OK |
| 400 | Parámetros inválidos |
| 401 | Sin token, token vencido o credenciales inválidas |
| 403 | Autenticado pero sin un grupo permitido |
| 404 | No existe |

Los errores de DRF tienen la forma `{"detail": "mensaje"}`.

## Capas de peligro de incendio (GeoServer)
Los mapas no salen de esta API: se piden directamente a GeoServer, sin token, en
`https://geoservicios.inamhi.gob.ec/geoserver/`. Ver la sección **GeoServer** al final.
""",
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
        'api.openapi_geoserver.agregar_geoserver',
    ],
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    'SERVE_AUTHENTICATION': [],
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api_incendios/',
    'SWAGGER_UI_SETTINGS': {
        'persistAuthorization': True,
        'displayRequestDuration': True,
        'docExpansion': 'list',
    },
    'TAGS': [
        {'name': 'Autenticación', 'description': 'Login, renovación de token y datos del usuario.'},
        {'name': 'Áreas protegidas', 'description': 'Áreas protegidas con su alerta vigente (público).'},
        {'name': 'Alertas', 'description': 'Alertas de incendio del modelo, GOES, FIRMS y reportes validados (público).'},
        {'name': 'Focos de calor', 'description': 'Detecciones satelitales de VIIRS (NASA FIRMS) y GOES-19 en todo Ecuador continental (público).'},
        {'name': 'Reportes', 'description': 'Reportes de incendio desde la app y su validación (requiere login).'},
        {'name': 'Tiempo real', 'description': 'Estaciones automáticas: último dato e historial (público, solo lectura).'},
        {'name': 'GeoServer', 'description': 'Capas de peligro de incendio: WMS y WFS públicos, servidos por GeoServer.'},
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