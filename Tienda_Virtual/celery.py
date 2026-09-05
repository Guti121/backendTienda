



import os
from celery import Celery

# Default de desarrollo, igual que manage.py/wsgi.py. En producción se exporta
# DJANGO_SETTINGS_MODULE=Tienda_Virtual.settings.production antes de arrancar el worker.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tienda_Virtual.settings.local')

# Crea la instancia de Celery
app = Celery('Tienda_Virtual')

# Carga la configuración de Django en Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# La zona horaria se toma de CELERY_TIMEZONE (= TIME_ZONE) vía config_from_object.

# Auto-descubre tareas en todos los apps (apps/*/tasks.py)
app.autodiscover_tasks()


from celery.schedules import crontab

# Fuente única de las tareas programadas: este dict (versionado). django_celery_beat
# sigue instalado pero NO se usa; si algún día se quiere editar horarios sin
# desplegar, arrancar beat con --scheduler django_celery_beat.schedulers:DatabaseScheduler.
app.conf.beat_schedule = {
    'generar-reporte-ventas-cada-noche': {
        'task': 'apps.inventario.tasks.generar_reporte_ventas_dia',
        'schedule': crontab(minute=59, hour=23),
    },
    'generar-reporte-ventas-mensual': {
        'task': 'apps.inventario.tasks.generar_reporte_ventas_mes',
        'schedule': crontab(minute=0, hour=3, day_of_month='1'),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

