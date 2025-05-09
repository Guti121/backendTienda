from django.db.models.signals import post_delete
from django.dispatch import receiver
from apps.shoppingcart.models import FacturaDetalle
from apps.inventario.models import ReporteVentasDiario
from apps.inventario.tasks import generar_reporte_ventas_dia_update
from django.utils import timezone

@receiver(post_delete, sender=FacturaDetalle)
def actualizar_reporte_ventas(sender, instance, **kwargs):
    print(f"FacturaDetalle con ID {instance.id} ha sido eliminada, actualizando reporte de ventas...")

    if instance.creado_en and instance.tienda:
        fecha = instance.creado_en.date()
        company_id = instance.tienda.id
        print(company_id,'esta es mi tienda')
        generar_reporte_ventas_dia_update.apply_async(kwargs={
            'fecha': str(fecha),  # Convertido a string por seguridad de serialización
            'company': company_id
        })
    else:
        print("No se ejecutó la tarea porque falta fecha o compañía.")
