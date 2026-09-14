



import os
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

# Mismo criterio que manage.py/wsgi.py: DJANGO_SETTINGS_MODULE sale del .env
# (o del entorno real del server), nunca de editar este archivo. Default
# 'production': un worker que arranca sin esa variable debe fallar fuerte, no
# correr en silencio con settings de desarrollo.
load_dotenv(Path(__file__).resolve().parent.parent / '.env')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tienda_Virtual.settings.production')

# Crea la instancia de Celery
app = Celery('Tienda_Virtual')

# Carga la configuración de Django en Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# La zona horaria se toma de CELERY_TIMEZONE (= TIME_ZONE) vía config_from_object.

# Auto-descubre tareas en todos los apps (apps/*/tasks.py)
app.autodiscover_tasks()

# Sin beat_schedule: los reportes de inventario se calculan al leer (no hay
# tareas programadas). Celery se mantiene solo para tareas encoladas bajo
# demanda (p. ej. el código de barras en apps/colletion/tasks.py).


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

