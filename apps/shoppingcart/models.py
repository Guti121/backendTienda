from django.db import models
from apps.myStore.models import BaseModel
from apps.colletion.models import ProductModel


# Create your models here.
class Factura(BaseModel):
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'Factura {self.id} {self.fecha} '

class FacturaDetalle(BaseModel):
    factura = models.ForeignKey("shoppingcart.Factura", related_name='detalles', on_delete=models.CASCADE) 
    producto = models.ForeignKey("colletion.ProductModel", on_delete=models.SET_NULL, null=True, blank=True)
    nombre_producto = models.CharField(max_length=255)  # Nuevo campo para almacenar el nombre
    cantidad = models.PositiveIntegerField()
    valor_und=models.DecimalField(max_digits=10, decimal_places=2,blank=False)
    valor_mayor_und= models.DecimalField(max_digits=10,decimal_places=2)
    valor_con_CF = models.DecimalField(max_digits=10,decimal_places=2,blank=False)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        if self.producto:  
            self.nombre_producto = self.producto.nombre  # Guarda el nombre del producto antes de que pueda eliminarse
            self.valor_und=self.producto.valor #Guarda el valor del producto por unidad 
            self.valor_mayor_und=self.producto.valor_mayor
            if self.producto.valor_costos_fijos:
                self.valor_con_CF=self.producto.valor_costos_fijos
            else:
                self.valor_con_CF=0
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.id}, {self.cantidad}x {self.nombre_producto}'
