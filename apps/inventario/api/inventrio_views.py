from datetime import date
from apps.colletion.models import ProductModel
from rest_framework.response import Response
from rest_framework import status
from django.db.models import F, DecimalField, ExpressionWrapper, Sum

from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from apps.inventario.api.serializers.serializer import ReporteVentasDiarioSerializer, ReporteVentasMensualSerializer
#Vista para realizar el inventario actual
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.base.api.user.viewsPermissions import isCreator
from apps.inventario.models import ReporteVentasMensual,ReporteVentasDiario
from django.db.models.functions import ExtractMonth,ExtractYear
from Tienda_Virtual.globalFunctions import company_owner


class InventarioView(ListAPIView):
    serializer_class = ReporteVentasDiarioSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, isCreator]

    def get_queryset(self):
        user = self.request.user
        owner_company = company_owner(user)
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')

        # order_by explícito: sin él la paginación es inconsistente (warning de DRF).
        queryset = ReporteVentasDiario.objects.filter(tienda=owner_company).order_by('-fecha')

        if month and year:
            try:
                month = int(month)
                year = int(year)
                queryset = queryset.annotate(
                    month_field=ExtractMonth('fecha'),
                    year_field=ExtractYear('fecha')
                ).filter(month_field=month, year_field=year)
            except ValueError:
                pass  # Si no son números válidos, no filtramos

        return queryset

class InventarioMesView(ListAPIView):
    serializer_class = ReporteVentasMensualSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, isCreator]

    def get_queryset(self):
        user = self.request.user
        owner_company = company_owner(user)
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')

        queryset = ReporteVentasMensual.objects.filter(tienda=owner_company).order_by('-fecha')

        if month and year:
            try:
                month = int(month)
                year = int(year)
                queryset = queryset.annotate(
                    month_field=ExtractMonth('fecha'),
                    year_field=ExtractYear('fecha')
                ).filter(month_field=month, year_field=year)
            except ValueError:
                pass

        return queryset




class ResumenVentasMensualView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, isCreator]

    def get(self, request, *args, **kwargs):
        user = request.user
        owner_company = company_owner(user)

        # Recibir mes y año desde la URL o usar valores actuales por defecto
        try:
            month = int(request.query_params.get('month', date.today().month))
            year = int(request.query_params.get('year', date.today().year))
        except ValueError:
            return Response({"error": "El mes y año deben ser números válidos."},
                            status=status.HTTP_400_BAD_REQUEST)

        if not (1 <= month <= 12):
            return Response({"error": "El mes debe estar entre 1 y 12."},
                            status=status.HTTP_400_BAD_REQUEST)

        if not (2000 <= year <= date.today().year + 1):
            return Response({"error": "El año está fuera de rango."},
                            status=status.HTTP_400_BAD_REQUEST)

        reportes = ReporteVentasDiario.objects.annotate(
            mes_anno=ExtractMonth('fecha'),
            year_anno=ExtractYear('fecha')
        ).filter(
            mes_anno=month,
            year_anno=year,
            tienda=owner_company
        )

        resumen = reportes.aggregate(
            total_productos_vendidos=Sum('productos_vendidos'),
            total_valor_CF=Sum('total_valor_con_CF'),
            total_subtotal=Sum('total_subtotal'),
            total_valor_mayor=Sum('total_valor_mayor_und'),
        )

        return Response({
            "mes": month,
            "año": year,
            "tienda": owner_company.name,
            "resumen": {
                "productos_vendidos": resumen["total_productos_vendidos"] or 0,
                "costos_fijos_cubiertos": resumen["total_valor_CF"] or 0,
                "valor_al_por_mayor": resumen["total_valor_mayor"] or 0,
                "total_ventas": resumen["total_subtotal"] or 0,
            }
        }, status=status.HTTP_200_OK)
    

class InventarioProductos(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, isCreator]

    def get(self, request):
        """Valoración del stock activo (solo productos con disponible=True).

        Totales en pesos enteros (DecimalField), coherente con el resto del
        sistema sin centavos.
        """
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

    # Compat: la app llama por POST (sin cuerpo). Se mantiene como alias de GET.
    def post(self, request):
        return self.get(request)
