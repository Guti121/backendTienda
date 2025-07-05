import random
import barcode
from barcode.writer import ImageWriter
from django.core.files.base import ContentFile
from django.db import models,transaction
from io import BytesIO
from django.core.files import File
from apps.myStore.models import BaseModel

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
    
class ProductModel(BaseModel):
    nombre = models.CharField(max_length=100,unique=False,blank=False)
    tipo_producto = models.ForeignKey("colletion.TypeProductModel",related_name='Tipo_de_producto', on_delete=models.CASCADE)
    detalles = models.CharField(max_length=100)
    valor_mayor=models.DecimalField(max_digits=10, decimal_places=2,blank=False)
    valor_costos_fijos=models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor = models.DecimalField(max_digits=10, decimal_places=2,blank=False)
    unidades_disponibles = models.PositiveIntegerField()
    disponible = models.BooleanField(default=True)
    image= models.ImageField(upload_to='productos',null=True)
    numero_producto = models.CharField(max_length=5, unique=True, null=False, blank=True)
    publicar = models.BooleanField(default=False)

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

        with transaction.atomic():
            if not Bar_codeModel.objects.filter(product=self, tienda=self.tienda).exists():
                print("Generando código de barras...")
                self.generarcodigo_barras(self.numero_producto, self.tienda, self.creado_por)

    def generate_unique_number(self, max_attempts=50):
        """Genera un número único de producto, verificando que no se repita en la misma tienda."""
        for _ in range(max_attempts):  # Intenta hasta 10 veces
            numero = str(random.randint(10000, 99999))  # 5 dígitos
            if not ProductModel.objects.filter(numero_producto=numero, tienda=self.tienda).exists():
                return numero  # Si encuentra un número único, lo devuelve

        # Si después de 10 intentos no encuentra un número único, lanza un error
        raise ValueError("No se pudo generar un número de producto único. Inténtelo de nuevo.")
            
    
    def generarcodigo_barras(self, numero_producto,tienda,creado_por):
        codigo_pais = "770"
        codigo_fabricante = "0123"
        codigo_producto = numero_producto
        
        # Crea el código sin control (sin el dígito de control)
        codigo_sin_control = codigo_pais + codigo_fabricante + codigo_producto
        
        # Crea el objeto EAN-13, que automáticamente calculará el dígito de control
        ean = barcode.get("ean13", codigo_sin_control, writer=ImageWriter())

        # Guardar la imagen de código de barras en un archivo en memoria
        buffer = BytesIO()
        ean.write(buffer, {'format': 'PNG'})
        buffer.seek(0)

        # Crear el objeto Bar_codeModel y guardarlo
        barcode_instance = Bar_codeModel(
            product=self,
            barcode=ContentFile(buffer.read(), name=f"barcode_{codigo_sin_control}.png"),  # Usar el código completo para el nombre del archivo
            code=ean.get_fullcode(),  # Guarda el código completo, incluyendo el dígito de control
            tienda=tienda,
            creado_por=creado_por
        )
        barcode_instance.save()  # Guardar el código de barras en la base de datos


    def __str__(self):
        return f'{self.id} , {self.nombre}, {self.unidades_disponibles}'
    

class Bar_codeModel(BaseModel):
    product = models.OneToOneField("colletion.ProductModel",related_name="producto", on_delete=models.CASCADE)
    barcode = models.ImageField(upload_to='barcodes/', null=True, blank=True)
    code =models.CharField(max_length=13, null=False, blank=False) 

    
    
    def __str__(self):
        return f'{self.id} , {self.product.nombre}'


#config precios productos de productModels

class Config_ProductModel(BaseModel):
    #costos fijos totales mensuales 
    costos_fijos=models.DecimalField(max_digits=10,decimal_places=2,blank=False)
    #margen de ganacia que desea ganar en todos los productos 
    margen_ganancia=models.DecimalField(max_digits=3,decimal_places=1,default=0)
    #Promedio de productos vendidas mensualmente 
    promedio_productos_vendidos=models.IntegerField(blank=False)

    disponible=models.BooleanField(default=True)

