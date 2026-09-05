"""Settings para la suite de tests. Rápido y sin servicios externos.

    python manage.py test --settings=Tienda_Virtual.settings.test
"""
import os
import tempfile

from .base import *  # noqa

DEBUG = False
ALLOWED_HOSTS = ['testserver']
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'test-secret-key-no-usar-en-prod')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Tareas Celery en el acto (sin broker ni worker).
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Hash de contraseñas rápido.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Media a un temporal (los tests suben imágenes de producto/logo).
MEDIA_ROOT = os.path.join(tempfile.gettempdir(), 'tienda_test_media')
MEDIA_URL = '/media/'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

# Menos ruido de logs durante los tests.
LOGGING['root']['level'] = 'WARNING'
for _logger in LOGGING['loggers'].values():
    _logger['level'] = 'WARNING'
