#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    """Run administrative tasks."""
    # DJANGO_SETTINGS_MODULE se decide por variable de entorno, NUNCA editando
    # este archivo a mano (ese hand-flip era el problema: si alguien lo dejaba
    # en 'local' y así se desplegaba, producción arrancaba con DEBUG=True).
    # Default 'production': si falta config real, production.py falla fuerte
    # en vez de arrancar silenciosamente como 'local'. Para desarrollo, poné en
    # tu .env (no versionado): DJANGO_SETTINGS_MODULE=Tienda_Virtual.settings.local
    load_dotenv(Path(__file__).resolve().parent / '.env')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tienda_Virtual.settings.production')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
