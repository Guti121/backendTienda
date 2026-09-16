from rest_framework import serializers

from Tienda_Virtual.globalFunctions import company_owner
from apps.colletion.models import DescuentoProducto


class DescuentoProductoSerializer(serializers.ModelSerializer):
    """Alta/edición de una promoción de producto."""

    class Meta:
        model = DescuentoProducto
        fields = ['id', 'producto', 'porcentaje', 'fecha_inicio', 'fecha_fin', 'activo']
        read_only_fields = ['id']

    def validate(self, data):
        fecha_inicio = data.get('fecha_inicio', getattr(self.instance, 'fecha_inicio', None))
        fecha_fin = data.get('fecha_fin', getattr(self.instance, 'fecha_fin', None))
        if fecha_inicio and fecha_fin and fecha_fin <= fecha_inicio:
            raise serializers.ValidationError(
                {"fecha_fin": "fecha_fin debe ser posterior a fecha_inicio."}
            )

        producto = data.get('producto', getattr(self.instance, 'producto', None))
        request = self.context.get('request')
        if producto is not None and request is not None:
            company = company_owner(request.user)
            if company and producto.tienda_id != company.id:
                raise serializers.ValidationError(
                    {"producto": "Este producto no pertenece a tu tienda."}
                )

        return data


class DescuentoProductoListSerializer(serializers.ModelSerializer):
    """Lectura: incluye si la promo está vigente ahora mismo."""

    vigente = serializers.SerializerMethodField()

    class Meta:
        model = DescuentoProducto
        fields = ['id', 'producto', 'porcentaje', 'fecha_inicio', 'fecha_fin', 'activo', 'vigente']

    def get_vigente(self, obj):
        return obj.vigente
