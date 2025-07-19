



import os
from celery import Celery

# Aquí configuras el DJANGO_SETTINGS_MODULE para tu proyecto  
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tienda_Virtual.settings.production')

# Crea la instancia de Celery 
app = Celery('Tienda_Virtual')

# Carga la configuración de Django en Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

app.conf.timezone = 'America/Bogota'  # Configura la zona horaria de Celery

# Auto-descubre tareas en todos los apps
app.autodiscover_tasks()


from celery.schedules import crontab

app.conf.beat_schedule = {
    'generar-reporte-ventas-cada-noche': {
        'task': 'apps.inventario.tasks.generar_reporte_ventas_dia',
        'schedule': crontab(minute=59, hour =23),#minute=59,hour=23
    },
    'generar-reporte-ventas-mensual': {
        'task': 'apps.inventario.tasks.generar_reporte_ventas_mes',
        'schedule': crontab(minute=0, hour=3, day_of_month='1'),#day_of_week=6, day_of_month='28-31'
    },
}



@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

