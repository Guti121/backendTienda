from .base  import *
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR/ '.env')
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG","False")=="True"

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS').split(',')

CORS_ALLOWED_ORIGINS =os.getenv('DJANGO_CORS_ALLOWED_ORIGINS').split(',')


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


# Configuración de Celery
CELERY_BROKER_URL = 'redis://localhost:6379/0'   # Usamos Redis como broker
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'  # También Redis para almacenar resultados
CELERY_TIMEZONE = 'America/Bogota'  # O la zona horaria que estés usando

