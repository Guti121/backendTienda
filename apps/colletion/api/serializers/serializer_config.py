

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

    # OJO: antes estos métodos estaban indentados dentro de `class Meta`, por lo
    # que Django/DRF nunca los ejecutaba. Ahora viven en el serializer.
    def validate(self, data):
        if data.get('costos_fijos') is None:
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