"""Rangos de fecha aware para filtrar DateTimeField sin depender de
fecha__year / __month / __date.

Esos lookups, con USE_TZ=True y MySQL, se traducen a CONVERT_TZ(...) y necesitan
las tablas de timezone del servidor cargadas; si faltan, devuelven NULL y el
filtro no matchea nada. Un rango [inicio, fin) se calcula en Python, no depende
de eso y aprovecha el índice de la columna.
"""
from datetime import datetime, time, timedelta

from django.utils import timezone


def month_bounds(year, month):
    """(inicio, fin) aware para [1 del mes, 1 del mes siguiente)."""
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime(year, month, 1), tz)
    if month == 12:
        fin = timezone.make_aware(datetime(year + 1, 1, 1), tz)
    else:
        fin = timezone.make_aware(datetime(year, month + 1, 1), tz)
    return inicio, fin


def day_bounds(d):
    """(inicio, fin) aware para el día `d` (date)."""
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(d, time.min), tz)
    return inicio, inicio + timedelta(days=1)
