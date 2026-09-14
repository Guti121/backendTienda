"""
WSGI config for Tienda_Virtual project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""
import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application
from dotenv import load_dotenv

# Mismo criterio que manage.py: DJANGO_SETTINGS_MODULE sale del entorno (.env
# junto a este repo, o variables reales del server), nunca de editar este
# archivo. Default 'production': si falta config, falla explícito en vez de
# servir tráfico real con settings de desarrollo (DEBUG=True, sin HTTPS...).
load_dotenv(Path(__file__).resolve().parent.parent / '.env')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tienda_Virtual.settings.production')

application = get_wsgi_application()

