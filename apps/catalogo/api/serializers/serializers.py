


from apps.colletion.api.serializers.serializer import ProductImageSerializer
from rest_framework import serializers

from apps.colletion.models import ProductModel, TypeProductModel


class CatalogoProductListSerializer(serializers.ModelSerializer):
    image_principal = serializers.SerializerMethodField()
    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'valor', 'image_principal', 'numero_producto','creado_en', 'modificado_en']

  
    def get_image_principal(self, obj):
        principal = obj.imagenes.filter(principal=True).first()
        if principal:
            return principal.imagen.url  # or use .imagen.name if you don't want the full URL
        return None



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
