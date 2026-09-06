from .base  import *
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR/ '.env')


def _required(name):
    """Devuelve la variable de entorno o falla con un mensaje claro al arrancar."""
    value = os.getenv(name)
    if not value:
        raise ImproperlyConfigured(f"Falta la variable de entorno obligatoria: {name}")
    return value


def _csv(name):
    return [item.strip() for item in _required(name).split(',') if item.strip()]


SECRET_KEY = _required('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

ALLOWED_HOSTS = _csv('DJANGO_ALLOWED_HOSTS')

CORS_ALLOWED_ORIGINS = _csv('DJANGO_CORS_ALLOWED_ORIGINS')


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

# Ruta para servir archivos estáticos en desarrollo y producción
STATIC_URL = '/static/'

# Ruta absoluta donde se recogerán los archivos estáticos al hacer collectstatic
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

#config https 
# settings.py

SECURE_SSL_REDIRECT = True
SECURE_BROWSER_XSS_FILTER = True

# Activa HSTS y establece un tiempo de expiración
SECURE_HSTS_SECONDS = 31536000  # 1 año en segundos
SECURE_HSTS_INCLUDE_SUBDOMAINS = True  # Asegura que todos los subdominios también usen HTTPS
SECURE_HSTS_PRELOAD = True  # Indica que tu dominio puede ser pre-cargado por los navegadores (opcional)


# settings.py

# Evitar que los navegadores muestren contenido mixto (HTTPS + HTTP)
SECURE_CONTENT_TYPE_NOSNIFF = True

# Forzar el uso de cookies seguras
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True


# Celery: la config base está en base.py (broker/backend por env, default Redis
# local). Aquí no hace falta nada salvo, si se quiere, sobreescribir por env.

# No es necesario configurar un directorio local con S3
MEDIA_ROOT = None  	
#onfiguración de S3
AWS_ACCESS_KEY_ID = _required('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = _required('AWS_SECRET_ACCESS_KEY')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')  # Cambia por tu región
AWS_STORAGE_BUCKET_NAME = _required('AWS_STORAGE_BUCKET_NAME')


AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

# URL base para acceder a los archivos de medios
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'

CORS_ALLOW_CREDENTIALS = True

# STORAGES es la forma vigente (STATICFILES_STORAGE / DEFAULT_FILE_STORAGE se
# quitaron en Django 5.1).
STORAGES = {
    'staticfiles': {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
    },
    'default': {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
    },
}

# Otros ajustes
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

