"""
ASGI config for Tienda_Virtual project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from pathlib import Path

from django.core.asgi import get_asgi_application
from dotenv import load_dotenv

# Ver wsgi.py: DJANGO_SETTINGS_MODULE sale del .env, nunca de editar este archivo.
load_dotenv(Path(__file__).resolve().parent.parent / '.env')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tienda_Virtual.settings.production')

application = get_asgi_application()
