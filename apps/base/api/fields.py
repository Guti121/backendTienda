"""Campos DRF compartidos."""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from rest_framework import serializers


class PesosField(serializers.DecimalField):
    """Importe en pesos colombianos: entero, sin centavos.

    A diferencia de un `DecimalField(decimal_places=0)` normal, no rechaza una
    entrada con decimales: la redondea al peso más cercano (HALF_UP). Así el
    front puede seguir mandando "1234.56" y se guarda 1235.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", 0)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        try:
            data = Decimal(str(data)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        except (InvalidOperation, TypeError, ValueError):
            # que DRF lance su error normal ("Se requiere un número válido.")
            pass
        return super().to_internal_value(data)
