import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generar_codigo_barras_task(self, product_id):
    """Genera el código de barras EAN-13 de un producto (render PNG + guardado).

    Se encola desde `ProductModel.save()` con `transaction.on_commit`, así que el
    producto ya está commiteado cuando corre. Idempotente y tolerante a que el
    producto haya sido borrado entre el encolado y la ejecución.
    """
    from apps.colletion.models import Bar_codeModel, ProductModel

    try:
        producto = ProductModel.objects.select_related('tienda', 'creado_por').get(pk=product_id)
    except ProductModel.DoesNotExist:
        logger.warning("generar_codigo_barras_task: el producto %s ya no existe", product_id)
        return

    if Bar_codeModel.objects.filter(product=producto).exists():
        return

    try:
        producto.crear_codigo_barras()
    except Exception as exc:  # noqa: BLE001 - queremos reintentar ante cualquier fallo
        logger.exception("Fallo generando el código de barras del producto %s", product_id)
        raise self.retry(exc=exc)

    logger.info("Código de barras generado para el producto %s", product_id)
