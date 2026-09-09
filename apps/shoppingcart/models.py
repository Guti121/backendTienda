from django.db import models
from apps.myStore.models import BaseModel
from apps.colletion.models import ProductModel


# Create your models here.
class Factura(BaseModel):
    fecha = models.DateTimeField(auto_now_add=True)
    # Pesos colombianos: sin centavos.
    total = models.DecimalField(max_digits=10, decimal_places=0)

    def __str__(self):
        return f'Factura {self.id} {self.fecha} '

class FacturaDetalle(BaseModel):
    factura = models.ForeignKey("shoppingcart.Factura", related_name='detalles', on_delete=models.CASCADE) 
    producto = models.ForeignKey("colletion.ProductModel", on_delete=models.SET_NULL, null=True, blank=True)
    nombre_producto = models.CharField(max_length=255)  # Nuevo campo para almacenar el nombre
    cantidad = models.PositiveIntegerField()
    valor_und=models.DecimalField(max_digits=10, decimal_places=0,blank=False)
    valor_mayor_und= models.DecimalField(max_digits=10,decimal_places=0)
    valor_con_CF = models.DecimalField(max_digits=10,decimal_places=0,blank=False)
    subtotal = models.DecimalField(max_digits=10, decimal_places=0)

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
