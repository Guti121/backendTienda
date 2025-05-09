from rest_framework import serializers

from apps.colletion.models import ProductModel


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



