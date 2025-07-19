
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.core.files.storage import default_storage
from .models import Bar_codeModel
from .models import ProductModel
@receiver(post_delete, sender=Bar_codeModel)
def delete_barcode_file(sender, instance, **kwargs):
    """
    Cuando se borra un Bar_codeModel, eliminamos el archivo de S3.
    """
    if instance.barcode:
        instance.barcode.delete(save=False)



@receiver(post_delete, sender=ProductModel)
def eliminar_imagen_s3(sender, instance, **kwargs):
    if instance.imagen:  # o el campo de imagen que tengas
        instance.imagen.delete(save=False)
