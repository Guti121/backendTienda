import random
import barcode
from barcode.writer import ImageWriter
from django.core.files.base import ContentFile
from django.db import models,transaction
from io import BytesIO
from django.core.files import File
from apps.myStore.models import BaseModel
from django.core.exceptions import ValidationError


from uuid import uuid4

def upload_to_product_image(instance, filename):
    tienda_nombre = instance.producto.tienda.name.replace(" ", "_").lower()
    extension = filename.split(".")[-1]
    nombre_archivo = f"{uuid4().hex}.{extension}"
    return f"productos/{tienda_nombre}/{nombre_archivo}"


class TypeProductModel(BaseModel):
    tipo_producto=models.CharField(max_length=50,blank=False)
    detalles = models.CharField(max_length=500, blank=True, null=True)


    def save(self, *args, **kwargs):
        self.tipo_producto = self.tipo_producto.capitalize()  # Convertir la primera letra en mayúscula

        # Verificar si la tienda está definida
        if not self.tienda:
            raise ValueError("No se puede guardar un producto sin una tienda.")

        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.id} , {self.tipo_producto}"




class ProductImage(BaseModel):
    producto = models.ForeignKey("colletion.ProductModel", on_delete=models.CASCADE, related_name='imagenes')
    imagen = models.ImageField(upload_to=upload_to_product_image)
    principal = models.BooleanField(default=False)

    def clean(self):
        if self.producto.imagenes.count() >= 5 and not self.pk:
            raise ValidationError("Este producto ya tiene 5 imágenes.")
        
        if self.principal:
            otras = self.producto.imagenes.exclude(pk=self.pk)
            if otras.filter(principal=True).exists():
                raise ValidationError("Solo una imagen puede ser principal.")

    def save(self, *args, **kwargs):
        self.clean()
        if not self.producto.imagenes.exclude(pk=self.pk).filter(principal=True).exists():
            self.principal = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Imagen de {self.producto.nombre}"

    
class ProductModel(BaseModel):
    nombre = models.CharField(max_length=100,unique=False,blank=False)
    tipo_producto = models.ForeignKey("colletion.TypeProductModel",related_name='Tipo_de_producto', on_delete=models.CASCADE)
    detalles = models.CharField(max_length=100)
    # Pesos colombianos: sin centavos (decimal_places=0).
    valor_mayor=models.DecimalField(max_digits=10, decimal_places=0,blank=False)
    valor_costos_fijos=models.DecimalField(max_digits=10, decimal_places=0, default=0)
    valor = models.DecimalField(max_digits=10, decimal_places=0,blank=False)
    unidades_disponibles = models.PositiveIntegerField()
    disponible = models.BooleanField(default=True)
    numero_producto = models.CharField(max_length=5, unique=False, null=False, blank=True, db_index=True)
    publicar = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['tienda', 'nombre']),
        ]

    def imagen_principal(self):
        return self.imagenes.filter(principal=True).first()

    def save(self, *args, **kwargs):
        # Capitalizar el nombre antes de guardar
        self.nombre = self.nombre.title()

        # Validar que tienda esté definida antes de guardar
        if not self.tienda:
            raise ValueError("El campo 'tienda' es obligatorio.")

        # Si no tiene número de producto, generarlo
        if not self.numero_producto:
            self.numero_producto = self.generate_unique_number()

        super().save(*args, **kwargs)

        # La generación del código de barras (render PNG + subida a almacenamiento)
        # se hace en una tarea Celery, ya con el producto commiteado. En local
        # (CELERY_TASK_ALWAYS_EAGER) corre en el acto; en prod, en el worker.
        if not Bar_codeModel.objects.filter(product=self).exists():
            product_id = self.pk

            def _encolar():
                from apps.colletion.tasks import generar_codigo_barras_task
                generar_codigo_barras_task.delay(product_id)

            transaction.on_commit(_encolar)

    def generate_unique_number(self, max_attempts=50):
        """Genera un número único de producto, verificando que no se repita en la misma tienda."""
        for _ in range(max_attempts):  # Intenta hasta 10 veces
            numero = str(random.randint(10000, 99999))  # 5 dígitos
            if not ProductModel.objects.filter(numero_producto=numero, tienda=self.tienda).exists():
                return numero  # Si encuentra un número único, lo devuelve

        # Si después de 10 intentos no encuentra un número único, lanza un error
        raise ValueError("No se pudo generar un número de producto único. Inténtelo de nuevo.")
            
    
    def crear_codigo_barras(self):
        """Genera y guarda el Bar_codeModel EAN-13 de este producto.

        Llamada desde `generar_codigo_barras_task` (Celery). Idempotente: si ya
        existe un código para el producto, no hace nada.
        """
        if Bar_codeModel.objects.filter(product=self).exists():
            return

        codigo_pais = "770"
        codigo_fabricante = "0123"
        codigo_sin_control = codigo_pais + codigo_fabricante + self.numero_producto

        # EAN-13 calcula solo el dígito de control
        ean = barcode.get("ean13", codigo_sin_control, writer=ImageWriter())

        buffer = BytesIO()
        ean.write(buffer, {'format': 'PNG'})
        buffer.seek(0)

        Bar_codeModel.objects.create(
            product=self,
            barcode=ContentFile(
                buffer.read(),
                name=f"barcode_{codigo_sin_control}_{self.tienda.name}.png",
            ),
            code=ean.get_fullcode(),
            tienda=self.tienda,
            creado_por=self.creado_por,
        )


    def __str__(self):
        return f'{self.id} , {self.nombre}, {self.unidades_disponibles}'
    

class Bar_codeModel(BaseModel):
    product = models.OneToOneField("colletion.ProductModel",related_name="producto", on_delete=models.CASCADE)
    barcode = models.ImageField(upload_to='barcodes/', null=True, blank=True)
    code = models.CharField(max_length=13, null=False, blank=False, db_index=True)  # lectura por scanner

    
    
    def __str__(self):
        return f'{self.id} , {self.product.nombre}'


#config precios productos de productModels

class Config_ProductModel(BaseModel):
    #costos fijos totales mensuales (pesos, sin centavos)
    costos_fijos=models.DecimalField(max_digits=10,decimal_places=0,blank=False)
    #margen de ganancia (PORCENTAJE, ej. 35.0 -> se divide entre 100 al usarlo).
    #Mantiene 1 decimal a propósito: es un %, no un importe.
    margen_ganancia=models.DecimalField(max_digits=3,decimal_places=1,default=0)
    #Promedio de productos vendidas mensualmente 
    promedio_productos_vendidos=models.IntegerField(blank=False)

    disponible=models.BooleanField(default=True)

