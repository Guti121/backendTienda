# Tienda Virtual — Backend

API REST (Django + DRF) multi-tenant para gestión de tiendas: catálogo,
códigos de barras EAN-13, facturación con control de stock, reportes de ventas
(calculados al leer, con caché) y catálogo público.

Análisis del proyecto y plan de optimización: **[`ANALISIS_Y_OPTIMIZACION.md`](ANALISIS_Y_OPTIMIZACION.md)**.

## Puesta en marcha (desarrollo)

```bash
python -m venv venv
venv/Scripts/activate           # Windows;  source venv/bin/activate en Linux/mac
pip install -r requirements.txt
cp .env.example .env            # y rellenar DB_* y DJANGO_SECRET_KEY
# En .env, descomentar para desarrollo:
#   DJANGO_SETTINGS_MODULE=Tienda_Virtual.settings.local

python manage.py migrate
python manage.py runserver
```

`manage.py`/`wsgi.py`/`celery.py` usan `Tienda_Virtual.settings.production` **por
defecto** — nunca se edita el módulo a mano en esos archivos. Lo que decide qué
settings correr es la variable `DJANGO_SETTINGS_MODULE` en tu `.env` (no
versionado, por-desarrollador): sin ella, todo intenta arrancar como producción
y falla explícito si faltan `DB_*`/`AWS_*`/`DJANGO_ALLOWED_HOSTS` reales; con
`DJANGO_SETTINGS_MODULE=Tienda_Virtual.settings.local` en tu `.env`, corre en
modo desarrollo (`CELERY_TASK_ALWAYS_EAGER = True` hace que las tareas de
Celery corran en el acto sin necesitar Redis ni worker).

## Settings

| Módulo | Uso |
|---|---|
| `settings/base.py` | Común (apps, DRF, JWT, Celery, logging) |
| `settings/local.py` | Desarrollo (no versionado) |
| `settings/test.py` | Suite de tests (SQLite en memoria, Celery eager) |
| `settings/production.py` | HTTPS/HSTS, S3, todo por variables de entorno |

## Tests

```bash
python manage.py test --settings=Tienda_Virtual.settings.test
```

En CI (`.github/workflows/ci.yml`) corre en cada push/PR.

## Celery (cuando se necesite el flujo asíncrono real)

Solo hace falta el `worker` (código de barras bajo demanda). No hay
`beat_schedule`: los reportes de inventario se calculan al leer desde
`FacturaDetalle`, con caché (ver `apps/inventario/api/cache.py`).

```bash
# En otra terminal, con Redis levantado y CELERY_TASK_ALWAYS_EAGER=False:
celery -A Tienda_Virtual worker -l info
```

## Comandos útiles

```bash
python manage.py backfill_barcodes --dry-run   # productos sin código de barras
python manage.py backfill_barcodes --sync      # generarlos en el acto
```
