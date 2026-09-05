import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver
from apps.shoppingcart.models import FacturaDetalle
from apps.inventario.tasks import generar_reporte_ventas_dia_update

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=FacturaDetalle)
def actualizar_reporte_ventas(sender, instance, **kwargs):
    logger.info("FacturaDetalle %s eliminada, actualizando reporte de ventas...", instance.id)

    if instance.creado_en and instance.tienda:
        fecha = instance.creado_en.date()
        company_id = instance.tienda.id
        generar_reporte_ventas_dia_update.apply_async(kwargs={
            'fecha': str(fecha),  # Convertido a string por seguridad de serialización
            'company': company_id
        })
    else:
        logger.warning("No se ejecutó la tarea: falta fecha o compañía en FacturaDetalle %s", instance.id)
