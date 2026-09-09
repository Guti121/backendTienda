from rest_framework import serializers

from apps.inventario.models import ReporteVentasDiario, ReporteVentasMensual


class ReporteVentasDiarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReporteVentasDiario
        fields = ['fecha', 'facturas_total', 'productos_vendidos', 'total_subtotal']


class ReporteVentasMensualSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReporteVentasMensual
        fields = ['fecha', 'facturas_total', 'productos_vendidos',
                  'total_valor_mayor_und', 'total_valor_con_CF', 'total_subtotal']
