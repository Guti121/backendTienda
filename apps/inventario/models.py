from django.db import models

# Create your models here.
# apps/inventario/models.py

class ReporteVentasDiario(models.Model):
    tienda = models.ForeignKey('myStore.company', on_delete=models.CASCADE)
    fecha = models.DateField()  # Guardamos por día, un informe por día
    facturas_total = models.IntegerField(default=0)
    productos_vendidos = models.IntegerField(default=0)
    total_valor_mayor_und = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_valor_con_CF = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['tienda', 'fecha'])]

    def __str__(self):
        return f"Reporte del {self.fecha}, {self.tienda}"



class ReporteVentasMensual(models.Model): 
    tienda = models.ForeignKey('myStore.company', on_delete=models.CASCADE)
    fecha = models.DateField() # Guardamos el primer día del mes
    facturas_total = models.IntegerField(default=0)
    productos_vendidos = models.IntegerField(default=0)
    total_valor_mayor_und = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_valor_con_CF = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['tienda', 'fecha'])]

    def __str__(self):
        return f"Reporte del mes de {self.fecha.strftime('%B %Y')}, {self.tienda}"
