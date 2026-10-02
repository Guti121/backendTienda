from decimal import Decimal

from rest_framework import serializers

from ...models import CajaModel, MovimientoCajaModel


class CajaAbrirSerializer(serializers.ModelSerializer):
    monto_apertura = serializers.DecimalField(
        max_digits=10, decimal_places=0, min_value=Decimal("0"),
    )

    class Meta:
        model = CajaModel
        fields = ['monto_apertura']


class CajaSerializer(serializers.ModelSerializer):
    abierta_en = serializers.DateTimeField(source='creado_en', read_only=True)
    abierta_por = serializers.SerializerMethodField()
    cerrada_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = CajaModel
        fields = [
            'id', 'monto_apertura', 'abierta_en', 'abierta_por',
            'cerrada_en', 'monto_cierre_declarado', 'monto_cierre_esperado',
            'diferencia', 'cerrada_por_nombre', 'nota_cierre',
        ]

    def get_abierta_por(self, obj):
        if obj.creado_por:
            return f"{obj.creado_por.first_name} {obj.creado_por.last_name}".strip()
        return None

    def get_cerrada_por_nombre(self, obj):
        if obj.cerrada_por:
            return f"{obj.cerrada_por.first_name} {obj.cerrada_por.last_name}".strip()
        return None


class CajaCerrarSerializer(serializers.Serializer):
    monto_cierre_declarado = serializers.DecimalField(
        max_digits=10, decimal_places=0, min_value=Decimal("0"),
    )
    nota_cierre = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )


class MovimientoCajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoCajaModel
        fields = ['id', 'tipo', 'monto', 'motivo', 'creado_en']
        read_only_fields = ['id', 'creado_en']

    def validate_monto(self, value):
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a 0.")
        return value
