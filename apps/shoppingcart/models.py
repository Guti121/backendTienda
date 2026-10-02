from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from apps.myStore.models import BaseModel
from apps.colletion.models import ProductModel


class CajaModel(BaseModel):
    """Turno de caja: apertura/cierre de efectivo por tienda. `creado_en` (de
    BaseModel) es la apertura; `creado_por`, quien la abrió."""
    monto_apertura = models.DecimalField(max_digits=10, decimal_places=0)
    cerrada_en = models.DateTimeField(null=True, blank=True)
    monto_cierre_declarado = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    monto_cierre_esperado = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    diferencia = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    cerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cajas_cerradas",
    )
    nota_cierre = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=['tienda', 'cerrada_en'])]
        # Nota: MySQL no soporta UniqueConstraint con `condition` (lo ignora
        # con un warning W036), así que "solo una caja abierta por tienda" se
        # garantiza a nivel de aplicación (select_for_update en CajaAbrirView),
        # no con un constraint de BD.

    def __str__(self):
        return f"Caja {self.id} ({self.tienda_id})"


class MovimientoCajaModel(BaseModel):
    TIPO_CHOICES = [("ingreso", "Ingreso"), ("retiro", "Retiro")]
    caja = models.ForeignKey("shoppingcart.CajaModel", related_name="movimientos", on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=10, decimal_places=0)
    motivo = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.tipo} {self.monto} (caja {self.caja_id})"


# Create your models here.
class Factura(BaseModel):
    fecha = models.DateTimeField(auto_now_add=True)
    # Pesos colombianos: sin centavos. `subtotal` es la suma de las líneas ya
    # con su propio descuento aplicado; `total` es lo que pagó el cliente
    # (subtotal menos `descuento_porcentaje`, el descuento general de la venta).
    subtotal = models.DecimalField(max_digits=10, decimal_places=0)
    total = models.DecimalField(max_digits=10, decimal_places=0)
    descuento_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    METODO_PAGO_CHOICES = [
        ("efectivo", "Efectivo"),
        ("datafono", "Datáfono"),
        ("transferencia", "Transferencia"),
        ("sistecredito", "Sistecredito"),
        ("adi", "Adi"),
    ]
    metodo_pago = models.CharField(
        max_length=20, choices=METODO_PAGO_CHOICES, default="efectivo",
    )
    # Caja (turno) en la que se registró la venta — la asigna el servidor al
    # facturar (ver FacturasCreateView.perform_create), nunca el cliente.
    # Nullable: facturas de antes de esta feature no tienen caja asociada.
    caja = models.ForeignKey(
        "shoppingcart.CajaModel", related_name="facturas",
        null=True, blank=True, on_delete=models.PROTECT,
    )

    def __str__(self):
        return f'Factura {self.id} {self.fecha} '

class FacturaDetalle(BaseModel):
    factura = models.ForeignKey("shoppingcart.Factura", related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey("colletion.ProductModel", on_delete=models.SET_NULL, null=True, blank=True)
    nombre_producto = models.CharField(max_length=255)  # Nuevo campo para almacenar el nombre
    cantidad = models.PositiveIntegerField()
    valor_und=models.DecimalField(max_digits=10, decimal_places=0,blank=False)
    # valor_mayor_und y valor_con_CF guardan el TOTAL de la línea (precio * cantidad),
    # no el unitario; el sufijo `_und` es histórico. Ver save() más abajo.
    valor_mayor_und= models.DecimalField(max_digits=10,decimal_places=0)
    valor_con_CF = models.DecimalField(max_digits=10,decimal_places=0,blank=False)
    # subtotal: total de la línea YA con este descuento aplicado.
    subtotal = models.DecimalField(max_digits=10, decimal_places=0)
    # % realmente aplicado a esta línea (override del cajero, o si no vino la
    # promo vigente del producto al momento de la venta, o si no 0). Snapshot:
    # no se recalcula si la promo cambia después (ver save() más abajo).
    descuento_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        # Los reportes de inventario agregan por (tienda, rango de creado_en).
        indexes = [models.Index(fields=['tienda', 'creado_en'], name='fd_tienda_creado_idx')]

    def save(self, *args, **kwargs):
        # Solo al CREAR: se congelan los valores del producto (snapshot histórico).
        # En un update posterior NO se re-copian, para no reescribir el importe de
        # una factura ya emitida si el producto cambió de precio.
        if self._state.adding and self.producto:
            self.nombre_producto = self.producto.nombre
            self.valor_und = self.producto.valor
            self.valor_mayor_und = self.producto.valor_mayor * self.cantidad
            self.valor_con_CF = (self.producto.valor_costos_fijos or 0) * self.cantidad
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.id}, {self.cantidad}x {self.nombre_producto}'
