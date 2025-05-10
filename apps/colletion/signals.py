from django.db.models.signals import post_delete
from django.dispatch import receiver
from Tienda_Virtual.apps.colletion.models import ProductModel

@receiver(post_delete, sender=ProductModel)
def delete_product_barcode(sender, instance, **kwargs):
    # Verificar si el producto tiene un código de barras asociado
    if hasattr(instance, 'producto') and instance.producto and instance.producto.barcode:
        # Eliminar el archivo de código de barras
        instance.producto.barcode.delete(save=False)
        # Eliminar la instancia del modelo Bar_codeModel
        instance.producto.delete()