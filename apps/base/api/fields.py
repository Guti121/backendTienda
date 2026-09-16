"""Campos DRF compartidos."""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from rest_framework import serializers


def redondear_pesos(valor):
    """Redondea un importe en pesos colombianos al entero más cercano (HALF_UP).

    Único punto de redondeo de dinero, reusado por `PesosField` y por el
    cálculo de descuentos (producto/factura) para que ambos redondeen igual.
    """
    return Decimal(valor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


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
            data = redondear_pesos(Decimal(str(data)))
        except (InvalidOperation, TypeError, ValueError):
            # que DRF lance su error normal ("Se requiere un número válido.")
            pass
        return super().to_internal_value(data)
