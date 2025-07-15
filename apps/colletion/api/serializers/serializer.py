from email.mime import image
from typing import Required
from django.utils import timezone
import time
from Tienda_Virtual.globalFunctions import company_owner
from rest_framework import serializers
from ...models import ProductImage, ProductModel,TypeProductModel


#.............................................................................
""".............Se realizan los serializadores para Product..........."""
# serializers.py
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['imagen', 'principal']


class ProductModelSerializer(serializers.ModelSerializer):
    imagenes = ProductImageSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = ProductModel
        fields = '__all__'

    def validate(self, data):
        required_fields = ['nombre', 'tipo_producto', 'detalles', 'valor', 'valor_mayor', 'unidades_disponibles']
        for field in required_fields:
            if not data.get(field):
                raise serializers.ValidationError({field: f"El campo '{field}' es requerido."})

        if data.get('valor') <= 0:
            raise serializers.ValidationError({"valor": "El valor debe ser mayor a 0."})

        if data.get('valor_mayor') <= 0:
            raise serializers.ValidationError({"valor_mayor": "El valor mayor debe ser mayor a 0."})

        if data.get('unidades_disponibles') < 0:
            raise serializers.ValidationError({"unidades_disponibles": "Las unidades disponibles no pueden ser negativas."})

        return data

    def create(self, validated_data):
        request = self.context.get('request')
        files = request.FILES.getlist('imagenes')  # recupera todos los archivos enviados
        company= company_owner(request.user)
        producto = ProductModel.objects.create(**validated_data)

        if len(files) > 5:
            raise serializers.ValidationError("No puedes subir más de 5 imágenes por producto.")

        for idx, image_file in enumerate(files):
            ProductImage.objects.create(
                producto=producto,
                imagen=image_file,
                tienda=company,  # Asigna la tienda del usuario
                creado_por=request.user,  # Asigna el usuario que crea el producto
                creado_en=timezone.now(),
                principal=(idx == 0)  # la primera imagen como principal
            )

        return producto



#serializador para listFilter View
class ProductModelListFilterSerializer(serializers.ModelSerializer):
    imagen_principal = serializers.SerializerMethodField()

    class Meta:
        model = ProductModel
        fields = ['id','imagen_principal','nombre','tipo_producto','detalles','valor','unidades_disponibles','numero_producto']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Aquí cambiamos el campo 'categoria' de ID a 'nombre'
        category_name = instance.tipo_producto.tipo_producto  
        representation['tipo_producto'] = category_name
        
        return representation
    
    def get_imagen_principal(self, obj):
        principal = obj.imagenes.filter(principal=True).first()
        if principal:
            return principal.imagen.url  # o usa .imagen.name si no quieres la URL completa
        return None


##serializador para retrieve product
class ProductModelRetrieveProductSerializer(serializers.ModelSerializer):
    imagenes = ProductImageSerializer(many=True, read_only=True)


    class Meta:
        model = ProductModel
        fields = ['id','imagenes','nombre','tipo_producto','detalles','valor','unidades_disponibles','numero_producto']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Aquí cambiamos el campo 'categoria' de ID a 'nombre'
        category_name = instance.tipo_producto.tipo_producto  
        representation['tipo_producto'] = category_name
        
        return representation
    
class ProductModelRetrieveProductCreatorSerializer(serializers.ModelSerializer):
    imagenes = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = ProductModel
        fields = ['id','nombre','imagenes','tipo_producto','detalles','valor','valor_mayor','valor_costos_fijos','unidades_disponibles','numero_producto','publicar']

    
    def get_imagen_principal(self, obj):
        imagen = obj.imagen_principal()
        return imagen.imagen.url if imagen else None
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Aquí cambiamos el campo 'categoria' de ID a 'nombre'
        category_name = instance.tipo_producto.tipo_producto  
        representation['tipo_producto'] = category_name
        
        return representation
    
class ProductModelDestroySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductModel
        fields = 'id'

    def validate(self, data):
        # Realiza la validación de los campos requeridos
        if not data.get('id'):
            raise serializers.ValidationError("El campo 'id' es requerido.")
        
        return data


##serializer update Product
class ProductModelUpdateProductSerializer(serializers.ModelSerializer):
    imagenes = ProductImageSerializer( many=True, required=False,read_only=True)

    class Meta:
        model = ProductModel
        fields = [
            "nombre",
            "detalles",
            "valor_mayor",
            "valor_costos_fijos",
            "valor",
            "unidades_disponibles",
            "publicar",
            "imagenes"
        ]

  

#.............................................................................
""".............Se realizan los serializadores para Type Product..........."""


class TypeProductModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeProductModel
        fields = '__all__'

    def validate(self, data):
        # Realiza la validación de los campos requeridos
        if not data.get('tipo_producto'):
            raise serializers.ValidationError("El campo 'Tipo de producto' es requerido.")
        
        return data
    


class TypeProductModelDestroySerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeProductModel
        fields = 'id'

    def validate(self, data):
        # Realiza la validación de los campos requeridos
        if not data.get('id'):
            raise serializers.ValidationError("El campo 'id' es requerido.")
        
        return data
