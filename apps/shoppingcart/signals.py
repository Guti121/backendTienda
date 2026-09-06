import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from apps.shoppingcart.models import FacturaDetalle
from apps.inventario.tasks import generar_reporte_ventas_dia_update

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=FacturaDetalle)
def actualizar_reporte_ventas(sender, instance, **kwargs):
    """Al borrar un detalle de factura, recalcula el reporte diario de esa fecha.

    Se encola con transaction.on_commit: si el borrado hace rollback, la tarea no
    corre; y la tarea ve la BD ya sin el detalle (no datos obsoletos).
    """
    if not (instance.creado_en and instance.tienda_id):
        logger.warning("No se recalcula reporte: falta fecha o tienda en FacturaDetalle %s", instance.id)
        return

    fecha = str(instance.creado_en.date())
    company_id = instance.tienda_id
    transaction.on_commit(lambda: generar_reporte_ventas_dia_update.apply_async(
        kwargs={'fecha': fecha, 'company': company_id}
    ))
