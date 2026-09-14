"""Endpoint de salud: sin auth, ping mínimo a la BD. Lo usa el healthcheck de
Docker (servicio `web`) y sirve para monitoreo (uptime, balanceador) más
adelante."""
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse


def healthz(request):
    try:
        connections['default'].cursor()
    except OperationalError:
        return JsonResponse({"status": "error"}, status=503)
    return JsonResponse({"status": "ok"})
