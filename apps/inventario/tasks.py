from apps.myStore.models import Company
from celery import shared_task
from datetime import datetime
from django.utils import timezone
from apps.shoppingcart.models import FacturaDetalle
from apps.inventario.models import ReporteVentasDiario
from django.db.models import Sum
from datetime import timedelta

#Se realizan las funciones que generaran los reportes de las facturas manejados desde celery.py 

#generador de reportes diarios, llamado directamente desde celery.py
@shared_task
def generar_reporte_ventas_dia(fecha=None):
    print("Generando reportes de ventas del día por tienda...")

    hoy = fecha or timezone.now().date()

    inicio_del_dia = datetime.combine(hoy, datetime.min.time(), tzinfo=timezone.get_current_timezone())
    fin_del_dia = datetime.combine(hoy, datetime.max.time(), tzinfo=timezone.get_current_timezone())

    tiendas = Company.objects.all()

    for tienda in tiendas:
        ventas_hoy = FacturaDetalle.objects.filter(
            creado_en__range=(inicio_del_dia, fin_del_dia),
            factura__tienda=tienda
        )
        facturas_hoy = ventas_hoy.values('factura').distinct().count()

        reporte = ventas_hoy.aggregate(
            productos_vendidos=Sum('cantidad') or 0,
            total_valor_mayor_und=Sum('valor_mayor_und') or 0,
            total_valor_con_CF=Sum('valor_con_CF') or 0,
            total_subtotal=Sum('subtotal') or 0,
        )

        reporte_existente = ReporteVentasDiario.objects.filter(fecha=hoy, tienda=tienda).first()

        if reporte_existente:
            print(f"Actualizando reporte para {tienda.company} del día {hoy}...")
            reporte_existente.productos_vendidos = reporte['productos_vendidos'] or 0
            reporte_existente.total_valor_mayor_und = reporte['total_valor_mayor_und'] or 0
            reporte_existente.total_valor_con_CF = reporte['total_valor_con_CF'] or 0
            reporte_existente.total_subtotal = reporte['total_subtotal'] or 0
            reporte_existente.facturas_total = facturas_hoy
            reporte_existente.save()
        else:
            print(f"Creando reporte para {tienda.company} del día {hoy}...")
            ReporteVentasDiario.objects.create(
                fecha=hoy,
                tienda=tienda,
                productos_vendidos=reporte['productos_vendidos'] or 0,
                total_valor_mayor_und=reporte['total_valor_mayor_und'] or 0,
                total_valor_con_CF=reporte['total_valor_con_CF'] or 0,
                total_subtotal=reporte['total_subtotal'] or 0,
                facturas_total=facturas_hoy
            )

        print(f"Reporte de {tienda.company} para el día {hoy} {'actualizado' if reporte_existente else 'creado'} correctamente.")


#Actualiza los reportes cuando se elimina una factura, esta actualizacion ocurres si hay un reporte existente en la misma fecha de la factura eliminada, se llama 
#por un signal
@shared_task
def generar_reporte_ventas_dia_update(fecha=None, company=None):
    if not fecha or not company:
        print("⚠️ Parámetros 'fecha' y 'company' son requeridos. Tarea cancelada.")
        return

    print(f"📊 Generando reporte diario para tienda ID {company} en fecha {fecha}...")

    if isinstance(fecha, datetime):  # Verificamos si es un objeto `datetime`
        hoy = fecha.date()  # Si es `datetime`, extraemos solo la fecha
    else:
        hoy = datetime.fromisoformat(fecha).date()  # Si es una cadena, lo convertimos a `date`

    inicio = datetime.combine(hoy, datetime.min.time(), tzinfo=timezone.get_current_timezone())
    fin = datetime.combine(hoy, datetime.max.time(), tzinfo=timezone.get_current_timezone())

    try:
        tienda = Company.objects.get(id=company)
    except Company.DoesNotExist:
        print(f"❌ Tienda con ID {company} no existe.")
        return

    # Buscar el reporte existente
    reporte_existente = ReporteVentasDiario.objects.filter(fecha=hoy, tienda=tienda).first()
    if not reporte_existente:
        print(f"ℹ️ No existe reporte para {tienda.company} del {hoy}, no se realizó ninguna actualización.")
        return

    ventas = FacturaDetalle.objects.filter(
        creado_en__range=(inicio, fin),
        factura__tienda=tienda
    )

    facturas_hoy = ventas.values('factura').distinct().count() or 0

    reporte = ventas.aggregate(
        productos_vendidos=Sum('cantidad') or 0,
        total_valor_mayor_und=Sum('valor_mayor_und') or 0,
        total_valor_con_CF=Sum('valor_con_CF') or 0,
        total_subtotal=Sum('subtotal') or 0,
    )

    reporte_existente.productos_vendidos = reporte['productos_vendidos'] or 0
    reporte_existente.total_valor_mayor_und = reporte['total_valor_mayor_und'] or 0
    reporte_existente.total_valor_con_CF = reporte['total_valor_con_CF'] or 0
    reporte_existente.total_subtotal = reporte['total_subtotal'] or 0
    reporte_existente.facturas_total = facturas_hoy
    reporte_existente.save()

    print(f"🔄 Reporte actualizado para {tienda.company} del {hoy}.")

    # Ejecutar también el resumen mensual
    generar_reporte_ventas_mes_update.apply_async(kwargs={
        'fecha': hoy.isoformat(),
        'tienda_id': tienda.id
    })



from apps.inventario.models import ReporteVentasMensual

@shared_task
def generar_reporte_ventas_mes():
    print("Generando reportes de ventas mensuales por tienda...")

    hoy = timezone.now().date()

    primer_dia_mes = (hoy.replace(day=1) - timezone.timedelta(days=1)).replace(day=1)
    ultimo_dia_mes = hoy.replace(day=1) - timezone.timedelta(days=1)

    tiendas = Company.objects.all()

    for tienda in tiendas:
        reportes_diarios = ReporteVentasDiario.objects.filter(
            fecha__range=[primer_dia_mes, ultimo_dia_mes],
            tienda=tienda
        )

        reporte = reportes_diarios.aggregate(
            productos_vendidos=Sum('productos_vendidos') or 0,
            total_valor_mayor_und=Sum('total_valor_mayor_und') or 0,
            total_valor_con_CF=Sum('total_valor_con_CF') or 0,
            total_subtotal=Sum('total_subtotal') or 0,
            facturas_total=Sum('facturas_total') or 0,
        )

        reporte_existente = ReporteVentasMensual.objects.filter(fecha=primer_dia_mes, tienda=tienda).first()

        if reporte_existente:
            print(f"Actualizando reporte mensual de {tienda.company} para {primer_dia_mes.strftime('%B %Y')}...")
            reporte_existente.productos_vendidos = reporte['productos_vendidos'] or 0
            reporte_existente.total_valor_mayor_und = reporte['total_valor_mayor_und'] or 0
            reporte_existente.total_valor_con_CF = reporte['total_valor_con_CF'] or 0
            reporte_existente.total_subtotal = reporte['total_subtotal'] or 0
            reporte_existente.facturas_total = reporte['facturas_total'] or 0
            reporte_existente.save()
        else:
            print(f"Creando reporte mensual de {tienda.company} para {primer_dia_mes.strftime('%B %Y')}...")
            ReporteVentasMensual.objects.create(
                fecha=primer_dia_mes,
                tienda=tienda,
                productos_vendidos=reporte['productos_vendidos'] or 0,
                total_valor_mayor_und=reporte['total_valor_mayor_und'] or 0,
                total_valor_con_CF=reporte['total_valor_con_CF'] or 0,
                total_subtotal=reporte['total_subtotal'] or 0,
                facturas_total=reporte['facturas_total'] or 0
            )

        print(f"Reporte mensual de {tienda.company} para {primer_dia_mes.strftime('%B %Y')} {'actualizado' if reporte_existente else 'creado'} correctamente.")


@shared_task
def generar_reporte_ventas_mes_update(fecha=None, tienda_id=None):
    hoy = fecha or timezone.now().date()
    if isinstance(hoy, str):
        hoy = datetime.fromisoformat(hoy).date()

    primer_dia_mes = hoy.replace(day=1)
    ultimo_dia_mes = (primer_dia_mes + timezone.timedelta(days=32)).replace(day=1) - timezone.timedelta(days=1)

    tienda = Company.objects.get(id=tienda_id)

    try:
        reporte_mensual = ReporteVentasMensual.objects.get(fecha=primer_dia_mes, tienda=tienda)
    except ReporteVentasMensual.DoesNotExist:
        print(f"No existe reporte mensual para {tienda.company} en {primer_dia_mes.strftime('%Y-%m')}. No se actualiza.")
        return

    reportes = ReporteVentasDiario.objects.filter(
        tienda=tienda,
        fecha__range=[primer_dia_mes, ultimo_dia_mes]
    )

    suma = reportes.aggregate(
        productos_vendidos=Sum('productos_vendidos') or 0,
        total_valor_mayor_und=Sum('total_valor_mayor_und') or 0,
        total_valor_con_CF=Sum('total_valor_con_CF') or 0,
        total_subtotal=Sum('total_subtotal') or 0,
        facturas_total=Sum('facturas_total') or 0,
    )

    for k, v in suma.items():
        setattr(reporte_mensual, k, v or 0)
    reporte_mensual.save()
    print(f"Actualizado reporte mensual de {tienda.company}")


