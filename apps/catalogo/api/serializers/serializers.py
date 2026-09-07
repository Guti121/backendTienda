


from apps.colletion.api.serializers.serializer import ProductImageSerializer, _abs_media
from rest_framework import serializers

from apps.colletion.models import ProductModel, TypeProductModel


class CatalogoProductListSerializer(serializers.ModelSerializer):
    image_principal = serializers.SerializerMethodField()
    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'valor', 'image_principal', 'numero_producto','creado_en', 'modificado_en']

  
    def get_image_principal(self, obj):
        # Recorre en Python el prefetch 'imagenes' (evita el N+1 de .filter()).
        principal = next((img for img in obj.imagenes.all() if img.principal), None)
        return _abs_media(self, principal.imagen.url) if principal else None



class CatalogoProductRetrieveSerializer(serializers.ModelSerializer):
    imagenes = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'valor', 'imagenes', 'numero_producto', 'detalles', 'tipo_producto','creado_en','modificado_en']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')

        # Mostrar solo el nombre del tipo de producto
        if instance.tipo_producto:
            representation['tipo_producto'] = instance.tipo_producto.tipo_producto 

        return representation


class CatalogoTipoProductListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeProductModel
        fields = ['id','tipo_producto']
