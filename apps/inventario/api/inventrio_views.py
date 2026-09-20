"""Reportes de inventario calculados al leer desde `FacturaDetalle`.

Antes se servían de tablas precalculadas (`ReporteVentasDiario/Mensual`) que solo
llenaba Celery beat. Para el volumen del proyecto agregar en caliente por
tienda/periodo es de milisegundos con el índice `(tienda, creado_en)`; la
respuesta se cachea (ver `.cache`). Se usan rangos `[inicio, fin)` de
`Tienda_Virtual.dateutils` en vez de `__date` / `__month` (que en MySQL dependen
de las tz tables).
"""
import calendar
from datetime import date

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from Tienda_Virtual.dateutils import day_bounds, month_bounds
from Tienda_Virtual.globalFunctions import company_owner
from apps.base.api.user.viewsPermissions import isCreator
from apps.colletion.models import ProductModel
from apps.shoppingcart.models import Factura, FacturaDetalle

from .cache import cached_report

# valor_mayor_und / valor_con_CF son TOTALES de línea (precio * cantidad), no
# unitarios pese al nombre; ver FacturaDetalle.save().
_AGG = {
    "facturas_total": Count("factura", distinct=True),
    "productos_vendidos": Sum("cantidad"),
    "total_valor_mayor_und": Sum("valor_mayor_und"),
    "total_valor_con_CF": Sum("valor_con_CF"),
}


def _ventana(company, inicio, fin):
    """Agrega FacturaDetalle de una tienda en [inicio, fin).

    `total_subtotal` (lo vendido en pesos) sale de `Factura.total`, que ya
    descuenta el % general de la venta; sumar `FacturaDetalle.subtotal` lo
    ignoraría. Se agrega aparte para no inflar la suma con el join a detalles.
    """
    detalles = FacturaDetalle.objects.filter(
        tienda=company, creado_en__gte=inicio, creado_en__lt=fin
    )
    agg = detalles.aggregate(**_AGG)
    total = Factura.objects.filter(
        pk__in=detalles.values("factura")
    ).aggregate(t=Sum("total"))["t"]
    res = {k: (agg[k] or 0) for k in _AGG}
    res["total_subtotal"] = total or 0
    return res


def _mes_anio(request):
    """(month, year, error_response). Valores por defecto: mes/año actual."""
    hoy = date.today()
    try:
        month = int(request.query_params.get("month", hoy.month))
        year = int(request.query_params.get("year", hoy.year))
    except (TypeError, ValueError):
        return None, None, Response(
            {"error": "El mes y año deben ser números válidos."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not (1 <= month <= 12):
        return None, None, Response(
            {"error": "El mes debe estar entre 1 y 12."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not (2000 <= year <= hoy.year + 1):
        return None, None, Response(
            {"error": "El año está fuera de rango."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return month, year, None


def _paginated(request, view, filas):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(filas, request, view=view)
    return paginator.get_paginated_response(page)


class InventarioView(APIView):
    """GET /inventario/?month=&year=&page= — una fila por día con ventas."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, isCreator]

    def get(self, request):
        company = company_owner(request.user)
        month, year, err = _mes_anio(request)
        if err:
            return err

        def build():
            ndias = calendar.monthrange(year, month)[1]
            filas = []
            for d in range(ndias, 0, -1):  # más reciente primero
                dia = date(year, month, d)
                v = _ventana(company, *day_bounds(dia))
                if not v["facturas_total"]:
                    continue
                filas.append({
                    "fecha": dia.isoformat(),
                    "facturas_total": v["facturas_total"],
                    "productos_vendidos": v["productos_vendidos"],
                    "total_subtotal": v["total_subtotal"],
                })
            return filas

        filas = cached_report(company.id, f"daily:{year}-{month:02d}", build)
        return _paginated(request, self, filas)


class InventarioMesView(APIView):
    """GET /inventario/mensual/ — un mes concreto (?month=&year=) o los últimos 12."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, isCreator]

    def get(self, request):
        company = company_owner(request.user)

        def fila_mes(y, m):
            v = _ventana(company, *month_bounds(y, m))
            if not v["facturas_total"]:
                return None
            return {
                "fecha": date(y, m, 1).isoformat(),
                "facturas_total": v["facturas_total"],
                "productos_vendidos": v["productos_vendidos"],
                "total_valor_mayor_und": v["total_valor_mayor_und"],
                "total_valor_con_CF": v["total_valor_con_CF"],
                "total_subtotal": v["total_subtotal"],
            }

        if request.query_params.get("month") and request.query_params.get("year"):
            month, year, err = _mes_anio(request)
            if err:
                return err
            fila = cached_report(
                company.id, f"month:{year}-{month:02d}", lambda: fila_mes(year, month)
            )
            return _paginated(request, self, [fila] if fila else [])

        def build_12():
            hoy = date.today()
            y, m = hoy.year, hoy.month
            filas = []
            for _ in range(12):
                fila = fila_mes(y, m)
                if fila:
                    filas.append(fila)
                m -= 1
                if m == 0:
                    y, m = y - 1, 12
            return filas

        filas = cached_report(company.id, "monthly", build_12)
        return _paginated(request, self, filas)


class ResumenVentasMensualView(APIView):
    """GET /inventario/resumen/?month=&year= — totales agregados del mes."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, isCreator]

    def get(self, request):
        company = company_owner(request.user)
        month, year, err = _mes_anio(request)
        if err:
            return err

        v = cached_report(
            company.id, f"summary:{year}-{month:02d}",
            lambda: _ventana(company, *month_bounds(year, month)),
        )
        return Response({
            "mes": month,
            "año": year,
            "tienda": company.name,
            "resumen": {
                "productos_vendidos": v["productos_vendidos"],
                "costos_fijos_cubiertos": v["total_valor_con_CF"],
                "valor_al_por_mayor": v["total_valor_mayor_und"],
                "total_ventas": v["total_subtotal"],
            },
        }, status=status.HTTP_200_OK)


class InventarioProductos(APIView):
    """GET /inventario/productos/ — valoración del stock activo (disponible=True)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, isCreator]

    def get(self, request):
        owner_company = company_owner(request.user)
        pesos = DecimalField(max_digits=20, decimal_places=0)

        products = (
            ProductModel.objects
            .filter(tienda=owner_company, disponible=True)
            .annotate(
                subtotal_mayor=ExpressionWrapper(
                    F('unidades_disponibles') * F('valor_mayor'), output_field=pesos
                ),
                subtotal_venta=ExpressionWrapper(
                    F('unidades_disponibles') * F('valor'), output_field=pesos
                ),
                subtotal_costos=ExpressionWrapper(
                    F('unidades_disponibles') * F('valor_costos_fijos'), output_field=pesos
                ),
            )
        )

        totals = products.aggregate(
            total_unidades=Sum('unidades_disponibles'),
            total_precio_mayor=Sum('subtotal_mayor'),
            total_precio_venta=Sum('subtotal_venta'),
            total_costos_fijos=Sum('subtotal_costos'),
        )

        return Response({
            "total_unidades_disponibles": totals["total_unidades"] or 0,
            "total_precio_mayor": totals["total_precio_mayor"] or 0,
            "total_precio_venta": totals["total_precio_venta"] or 0,
            "total_costos_fijos": totals["total_costos_fijos"] or 0,
        })

    # Compat: la app llama por POST (sin cuerpo). Alias de GET.
    def post(self, request):
        return self.get(request)
