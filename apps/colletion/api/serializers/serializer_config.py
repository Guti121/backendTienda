from decimal import Decimal

from rest_framework import serializers
from apps.base.api.fields import PesosField
from apps.colletion.models import Config_ProductModel


_CONFIG_FIELDS = ['id', 'costos_fijos', 'margen_ganancia',
                  'promedio_productos_vendidos', 'disponible']


class CreateParametrosSerializer(serializers.ModelSerializer):
    # costos_fijos = pesos enteros (margen_ganancia es un %, se deja con decimal).
    costos_fijos = PesosField(max_digits=10, required=False)

    class Meta:
        model = Config_ProductModel
        fields = _CONFIG_FIELDS
        # 'disponible' decide qué config está activa: lo maneja el servidor.
        read_only_fields = ['id', 'disponible']

    # Validaciones de rango: sin ellas se podían guardar configs inservibles
    # (promedio 0 -> el cálculo siempre falla; costos_fijos negativos -> precio
    # sugerido menor que el coste). En update parcial los campos omitidos ni se
    # tocan ni se validan, así que solo se comprueba lo que llega.
    def validate_costos_fijos(self, v):
        if v is None or v <= 0:
            raise serializers.ValidationError(
                "Los costos fijos deben ser mayores que 0."
            )
        return v

    def validate_promedio_productos_vendidos(self, v):
        if v is None or v <= 0:
            raise serializers.ValidationError(
                "El promedio de productos vendidos debe ser mayor que 0."
            )
        return v

    def validate_margen_ganancia(self, v):
        if v is not None and (v < 0 or v > Decimal("999.9")):
            raise serializers.ValidationError(
                "El margen debe estar entre 0 y 999.9 %."
            )
        return v

    def validate(self, data):
        # En creación (no partial) costos_fijos es obligatorio.
        if not self.partial and data.get('costos_fijos') is None:
            raise serializers.ValidationError(
                {"costos_fijos": "El campo 'costos_fijos' es requerido."}
            )
        return data


class EliminacionParametrosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config_ProductModel
        fields = ['id']


class ListarParametrosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config_ProductModel
        fields = _CONFIG_FIELDS