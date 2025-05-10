from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Bar_codeModel  # Ajusta si está en otra app o nombre de modelo

@receiver(post_delete, sender=Bar_codeModel)
def delete_product_files(sender, instance, **kwargs):
    if instance.barcode:
        instance.barcode.delete(save=False)
