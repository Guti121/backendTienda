"""
WSGI config for Tienda_Virtual project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""
import os
from django.core.wsgi import get_wsgi_application
from dotenv import load_dotenv

# Cargar el archivo .env desde la nueva ubicación
dotenv_path = '/home/ubuntu/.env'
load_dotenv(dotenv_path)


# Establecer el módulo de configuración predeterminado
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tienda_Virtual.settings.production')

application = get_wsgi_application()

