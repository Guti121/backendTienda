from rest_framework import serializers

from apps.colletion.models import ProductModel
from apps.inventario.models import ReporteVentasDiario


class InventarioListFilterSerializer(serializers.Serializer):
    filter = serializers.CharField(max_length=100)  # Campo extra que no pertenece al modelo
    valor = serializers.CharField(max_length=100)  # Campo extra para usar en el filtro

    def validate_filter(self, value):
        # Comprobamos si el valor del filtro está entre los permitidos
        allowed_filters = ['nombre', 'tipo_producto', 'disponible']
        if value not in allowed_filters:
            raise serializers.ValidationError(
                f"El filtro '{value}' no es válido. Debe ser uno de {allowed_filters}."
            )
        return value





class ReporteVentasDiarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReporteVentasDiario
        fields = ['fecha', 'facturas_total', 'productos_vendidos','total_subtotal']


class ReporteVentasMensualSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReporteVentasDiario
        fields = ['fecha', 'facturas_total', 'productos_vendidos','total_valor_mayor_und', 'total_valor_con_CF', 'total_subtotal']

    