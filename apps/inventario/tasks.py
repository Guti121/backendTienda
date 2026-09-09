import logging
from django.utils.timezone import localtime  # ✅ El correcto
from apps.myStore.models import Company
from celery import shared_task
from datetime import datetime
from django.utils import timezone
from apps.shoppingcart.models import FacturaDetalle
from apps.inventario.models import ReporteVentasDiario
from django.db.models import Sum
from datetime import timedelta

logger = logging.getLogger(__name__)

#Se realizan las funciones que generaran los reportes de las facturas manejados desde celery.py

def _hoy_local():
    """Fecha actual en la zona horaria local.

    Se calcula en cada llamada (NO a nivel de módulo): el worker de Celery
    vive días, así que una variable de módulo quedaría congelada en la fecha
    de arranque del worker y todos los reportes saldrían con el día equivocado.
    """
    return localtime(timezone.now()).date()

#generador de reportes diarios, llamado directamente desde celery.py
@shared_task
def generar_reporte_ventas_dia(fecha=None):
    logger.info("Generando reportes de ventas del día por tienda...")
    hoy = fecha or _hoy_local()

    inicio_del_dia = datetime.combine(hoy, datetime.min.time(), tzinfo=timezone.get_current_timezone())
    fin_del_dia = datetime.combine(hoy, datetime.max.time(), tzinfo=timezone.get_current_timezone())

    tiendas = Company.objects.all()

    for tienda in tiendas:
        ventas_hoy = FacturaDetalle.objects.filter(
            creado_en__range=(inicio_del_dia, fin_del_dia),
            factura__tienda=tienda
        )

        reporte_existente = ReporteVentasDiario.objects.filter(fecha=hoy, tienda=tienda).first()

        # Sin ventas: no se crea una fila en cero. Si quedaba un reporte de una
        # pasada anterior (p. ej. se borraron todas las facturas del día), se
        # elimina para no dejar totales obsoletos.
        if not ventas_hoy.exists():
            if reporte_existente:
                logger.info(f"Sin ventas para {tienda.company} el {hoy}: se elimina el reporte.")
                reporte_existente.delete()
            continue

        facturas_hoy = ventas_hoy.values('factura').distinct().count()

        # valor_mayor_und / valor_con_CF son TOTALES de línea (precio * cantidad),
        # no unitarios pese al nombre; ver FacturaDetalle.save().
        reporte = ventas_hoy.aggregate(
            productos_vendidos=Sum('cantidad'),
            total_valor_mayor_und=Sum('valor_mayor_und'),
            total_valor_con_CF=Sum('valor_con_CF'),
            total_subtotal=Sum('subtotal'),
        )

        if reporte_existente:
            logger.info(f"Actualizando reporte para {tienda.company} del día {hoy}...")
            reporte_existente.productos_vendidos = reporte['productos_vendidos'] or 0
            reporte_existente.total_valor_mayor_und = reporte['total_valor_mayor_und'] or 0
            reporte_existente.total_valor_con_CF = reporte['total_valor_con_CF'] or 0
            reporte_existente.total_subtotal = reporte['total_subtotal'] or 0
            reporte_existente.facturas_total = facturas_hoy
            reporte_existente.save()
        else:
            logger.info(f"Creando reporte para {tienda.company} del día {hoy}...")
            ReporteVentasDiario.objects.create(
                fecha=hoy,
                tienda=tienda,
                productos_vendidos=reporte['productos_vendidos'] or 0,
                total_valor_mayor_und=reporte['total_valor_mayor_und'] or 0,
                total_valor_con_CF=reporte['total_valor_con_CF'] or 0,
                total_subtotal=reporte['total_subtotal'] or 0,
                facturas_total=facturas_hoy
            )

        logger.info(f"Reporte de {tienda.company} para el día {hoy} {'actualizado' if reporte_existente else 'creado'} correctamente.")


#Actualiza los reportes cuando se elimina una factura, esta actualizacion ocurres si hay un reporte existente en la misma fecha de la factura eliminada, se llama 
#por un signal
@shared_task
def generar_reporte_ventas_dia_update(fecha=None, company=None):
    if not fecha or not company:
        logger.info("⚠️ Parámetros 'fecha' y 'company' son requeridos. Tarea cancelada.")
        return

    logger.info(f"📊 Generando reporte diario para tienda ID {company} en fecha {fecha}...")

    if isinstance(fecha, datetime):  # Verificamos si es un objeto `datetime`
        hoy = fecha.date()  # Si es `datetime`, extraemos solo la fecha
    else:
        hoy = datetime.fromisoformat(fecha).date()  # Si es una cadena, lo convertimos a `date`

    inicio = datetime.combine(hoy, datetime.min.time(), tzinfo=timezone.get_current_timezone())
    fin = datetime.combine(hoy, datetime.max.time(), tzinfo=timezone.get_current_timezone())

    try:
        tienda = Company.objects.get(id=company)
    except Company.DoesNotExist:
        logger.info(f"❌ Tienda con ID {company} no existe.")
        return

    # Buscar el reporte existente
    reporte_existente = ReporteVentasDiario.objects.filter(fecha=hoy, tienda=tienda).first()
    if not reporte_existente:
        logger.info(f"ℹ️ No existe reporte para {tienda.company} del {hoy}, no se realizó ninguna actualización.")
        return

    ventas = FacturaDetalle.objects.filter(
        creado_en__range=(inicio, fin),
        factura__tienda=tienda
    )

    # Si ya no queda ninguna venta ese día, se elimina el reporte en vez de
    # dejarlo en cero.
    if not ventas.exists():
        logger.info(f"🗑️ Sin ventas restantes para {tienda.company} el {hoy}: se elimina el reporte.")
        reporte_existente.delete()
        generar_reporte_ventas_mes_update.apply_async(kwargs={
            'fecha': hoy.isoformat(),
            'tienda_id': tienda.id
        })
        return

    facturas_hoy = ventas.values('factura').distinct().count()

    reporte = ventas.aggregate(
        productos_vendidos=Sum('cantidad'),
        total_valor_mayor_und=Sum('valor_mayor_und'),
        total_valor_con_CF=Sum('valor_con_CF'),
        total_subtotal=Sum('subtotal'),
    )

    reporte_existente.productos_vendidos = reporte['productos_vendidos'] or 0
    reporte_existente.total_valor_mayor_und = reporte['total_valor_mayor_und'] or 0
    reporte_existente.total_valor_con_CF = reporte['total_valor_con_CF'] or 0
    reporte_existente.total_subtotal = reporte['total_subtotal'] or 0
    reporte_existente.facturas_total = facturas_hoy
    reporte_existente.save()

    logger.info(f"🔄 Reporte actualizado para {tienda.company} del {hoy}.")

    # Ejecutar también el resumen mensual
    generar_reporte_ventas_mes_update.apply_async(kwargs={
        'fecha': hoy.isoformat(),
        'tienda_id': tienda.id
    })



from apps.inventario.models import ReporteVentasMensual

@shared_task
def generar_reporte_ventas_mes():
    logger.info("Generando reportes de ventas mensuales por tienda...")

    hoy = _hoy_local()

    primer_dia_mes = (hoy.replace(day=1) - timezone.timedelta(days=1)).replace(day=1)
    ultimo_dia_mes = hoy.replace(day=1) - timezone.timedelta(days=1)

    tiendas = Company.objects.all()

    for tienda in tiendas:
        reportes_diarios = ReporteVentasDiario.objects.filter(
            fecha__range=[primer_dia_mes, ultimo_dia_mes],
            tienda=tienda
        )

        reporte_existente = ReporteVentasMensual.objects.filter(fecha=primer_dia_mes, tienda=tienda).first()

        # Sin diarios en el mes: no se crea mensual en cero; se borra el que
        # hubiera quedado de una pasada anterior.
        if not reportes_diarios.exists():
            if reporte_existente:
                logger.info(f"Sin diarios para {tienda.company} en {primer_dia_mes.strftime('%B %Y')}: se elimina el mensual.")
                reporte_existente.delete()
            continue

        reporte = reportes_diarios.aggregate(
            productos_vendidos=Sum('productos_vendidos'),
            total_valor_mayor_und=Sum('total_valor_mayor_und'),
            total_valor_con_CF=Sum('total_valor_con_CF'),
            total_subtotal=Sum('total_subtotal'),
            facturas_total=Sum('facturas_total'),
        )

        if reporte_existente:
            logger.info(f"Actualizando reporte mensual de {tienda.company} para {primer_dia_mes.strftime('%B %Y')}...")
            reporte_existente.productos_vendidos = reporte['productos_vendidos'] or 0
            reporte_existente.total_valor_mayor_und = reporte['total_valor_mayor_und'] or 0
            reporte_existente.total_valor_con_CF = reporte['total_valor_con_CF'] or 0
            reporte_existente.total_subtotal = reporte['total_subtotal'] or 0
            reporte_existente.facturas_total = reporte['facturas_total'] or 0
            reporte_existente.save()
        else:
            logger.info(f"Creando reporte mensual de {tienda.company} para {primer_dia_mes.strftime('%B %Y')}...")
            ReporteVentasMensual.objects.create(
                fecha=primer_dia_mes,
                tienda=tienda,
                productos_vendidos=reporte['productos_vendidos'] or 0,
                total_valor_mayor_und=reporte['total_valor_mayor_und'] or 0,
                total_valor_con_CF=reporte['total_valor_con_CF'] or 0,
                total_subtotal=reporte['total_subtotal'] or 0,
                facturas_total=reporte['facturas_total'] or 0
            )

        logger.info(f"Reporte mensual de {tienda.company} para {primer_dia_mes.strftime('%B %Y')} {'actualizado' if reporte_existente else 'creado'} correctamente.")


@shared_task
def generar_reporte_ventas_mes_update(fecha=None, tienda_id=None):
    hoy = fecha or _hoy_local()
    if isinstance(hoy, str):
        hoy = datetime.fromisoformat(hoy).date()

    primer_dia_mes = hoy.replace(day=1)
    ultimo_dia_mes = (primer_dia_mes + timezone.timedelta(days=32)).replace(day=1) - timezone.timedelta(days=1)

    tienda = Company.objects.get(id=tienda_id)

    try:
        reporte_mensual = ReporteVentasMensual.objects.get(fecha=primer_dia_mes, tienda=tienda)
    except ReporteVentasMensual.DoesNotExist:
        logger.info(f"No existe reporte mensual para {tienda.company} en {primer_dia_mes.strftime('%Y-%m')}. No se actualiza.")
        return

    reportes = ReporteVentasDiario.objects.filter(
        tienda=tienda,
        fecha__range=[primer_dia_mes, ultimo_dia_mes]
    )

    # Si ya no quedan diarios en el mes, se elimina el mensual en vez de dejarlo
    # en cero.
    if not reportes.exists():
        logger.info(f"Sin diarios en {primer_dia_mes.strftime('%Y-%m')} para {tienda.company}: se elimina el mensual.")
        reporte_mensual.delete()
        return

    suma = reportes.aggregate(
        productos_vendidos=Sum('productos_vendidos'),
        total_valor_mayor_und=Sum('total_valor_mayor_und'),
        total_valor_con_CF=Sum('total_valor_con_CF'),
        total_subtotal=Sum('total_subtotal'),
        facturas_total=Sum('facturas_total'),
    )

    for k, v in suma.items():
        setattr(reporte_mensual, k, v or 0)
    reporte_mensual.save()
    logger.info(f"Actualizado reporte mensual de {tienda.company}")


