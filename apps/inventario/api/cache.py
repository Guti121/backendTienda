"""Caché de los reportes de inventario.

Los endpoints agregan `FacturaDetalle` en caliente; la respuesta se cachea con
una clave versionada por tienda. `bump_tienda()` sube la versión y así invalida
de golpe todos los periodos cacheados de esa tienda (O(1)), sin recorrer claves.
El TTL es solo una red de seguridad.
"""
from django.core.cache import cache

DEFAULT_TTL = 600  # 10 min


def _ver_key(tienda_id):
    return f"inv:ver:{tienda_id}"


def _version(tienda_id):
    return cache.get(_ver_key(tienda_id)) or 1


def bump_tienda(tienda_id):
    """Invalida todos los reportes cacheados de la tienda."""
    if tienda_id is None:
        return
    key = _ver_key(tienda_id)
    try:
        cache.incr(key)
    except ValueError:  # la clave aún no existe
        cache.set(key, 2, None)


def cached_report(tienda_id, name, build_fn, ttl=DEFAULT_TTL):
    """Devuelve `build_fn()` cacheado bajo `inv:{name}:{tienda}:v{version}`."""
    key = f"inv:{name}:{tienda_id}:v{_version(tienda_id)}"
    data = cache.get(key)
    if data is None:
        data = build_fn()
        cache.set(key, data, ttl)
    return data
