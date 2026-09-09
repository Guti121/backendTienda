import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.inventario.api.cache import bump_tienda
from apps.shoppingcart.models import FacturaDetalle

logger = logging.getLogger(__name__)


@receiver(post_save, sender=FacturaDetalle)
@receiver(post_delete, sender=FacturaDetalle)
def invalidar_reportes_inventario(sender, instance, **kwargs):
    """Al crear/borrar una línea de factura, invalida los reportes cacheados de
    esa tienda. Los reportes se calculan al leer desde FacturaDetalle; el TTL de
    la caché es solo respaldo, esto los refresca al instante.

    Se hace en transaction.on_commit: si la operación hace rollback no se
    invalida de más, y la siguiente lectura recalcula sobre la BD ya consistente.
    """
    tienda_id = instance.tienda_id
    if not tienda_id:
        return
    transaction.on_commit(lambda: bump_tienda(tienda_id))
