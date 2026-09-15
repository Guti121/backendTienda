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


def _csv_optional(name, default=''):
    """Como _csv() pero sin exigir la variable: lista vacía si no está seteada."""
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


SECRET_KEY = _required('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

ALLOWED_HOSTS = _csv('DJANGO_ALLOWED_HOSTS')

CORS_ALLOWED_ORIGINS = _csv('DJANGO_CORS_ALLOWED_ORIGINS')
CORS_ALLOW_CREDENTIALS = True

# Solo importa para /admin/ (login por cookie de sesión + CSRF de Django); la
# API usa JWT (sin SessionAuthentication) y no pasa por esta validación.
# Opcional a propósito: mientras no haya dominio + HTTPS (SECURE_SSL_REDIRECT
# en False) el chequeo estricto de Referer ni se activa. Cuando haya dominio,
# el mismo que nginx sirve, con esquema:
# DJANGO_CSRF_TRUSTED_ORIGINS=https://tudominio.com
CSRF_TRUSTED_ORIGINS = _csv_optional('DJANGO_CSRF_TRUSTED_ORIGINS')


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '3306'),
        # Conexiones persistentes: con gunicorn multi-worker evita reabrir una
        # conexión MySQL en cada request. 0 (default de Django) = como antes.
        'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '60')),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}


#config https
# settings.py

# Detrás de nginx (reverse proxy) la conexión real del cliente puede ser HTTPS
# aunque nginx le hable a Django por HTTP simple. Sin esto, Django nunca ve la
# request como segura y SECURE_SSL_REDIRECT puede entrar en bucle de redirects.
# nginx debe mandar X-Forwarded-Proto (ver deploy/nginx/default.conf).
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Configurables por env porque, mientras no haya dominio + certbot, nginx solo
# sirve HTTP — forzar el redirect a HTTPS (o HSTS) dejaría el sitio
# inalcanzable. En el .env del VPS: DJANGO_SECURE_SSL_REDIRECT=False y
# DJANGO_SECURE_HSTS_SECONDS=0 hasta tener TLS; después se quitan (o se ponen
# en True / 31536000) para recuperar la protección completa.
SECURE_SSL_REDIRECT = os.getenv('DJANGO_SECURE_SSL_REDIRECT', 'True') == 'True'
SECURE_BROWSER_XSS_FILTER = True

# Activa HSTS y establece un tiempo de expiración
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_SECURE_HSTS_SECONDS', '31536000'))  # 1 año en segundos
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

# Caché: los reportes de inventario se calculan al leer y se cachean aquí. En
# dev queda el LocMemCache por defecto; en prod se usa Redis (ya requerido como
# broker). CACHE_REDIS_URL permite apuntar a otra instancia/db.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('CACHE_REDIS_URL', CELERY_BROKER_URL),
    }
}

# --- Estático y media ---
# Por defecto: filesystem local, en un volumen del compose que comparten
# `web` (lo escribe) y `nginx` (lo sirve directo, ver deploy/nginx/default.conf
# — bypassea a Django/gunicorn para esos paths, que es lo correcto en prod).
# Sin S3 no hace falta ninguna cuenta/credencial de AWS para arrancar.
#
# Si más adelante SÍ se quiere S3 (por ejemplo, correr varias instancias de
# `web` sin volumen compartido, o servir media desde un CDN): poner
# USE_S3=True + las 3 variables AWS_* en el .env. Nada más del código cambia
# (django-storages/boto3 ya están en requirements.txt).
USE_S3 = os.getenv('USE_S3', 'False') == 'True'

if USE_S3:
    AWS_ACCESS_KEY_ID = _required('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = _required('AWS_SECRET_ACCESS_KEY')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')  # Cambia por tu región
    AWS_STORAGE_BUCKET_NAME = _required('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'

    # STORAGES es la forma vigente (STATICFILES_STORAGE / DEFAULT_FILE_STORAGE
    # se quitaron en Django 5.1).
    STORAGES = {
        'staticfiles': {'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage'},
        'default': {'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage'},
    }
else:
    STATIC_URL = '/static/'
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # colectado por `collectstatic`
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')          # subido por los usuarios

    STORAGES = {
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    }

# Otros ajustes
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

