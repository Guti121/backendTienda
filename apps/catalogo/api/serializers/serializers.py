


from apps.colletion.api.serializers.serializer import (
    ProductImageSerializer, _abs_media, _descuento_porcentaje_de, _valor_con_descuento_de,
)
from rest_framework import serializers

from apps.colletion.models import ProductModel, TypeProductModel


class CatalogoProductListSerializer(serializers.ModelSerializer):
    image_principal = serializers.SerializerMethodField()
    # Nombre del tipo de producto (para agrupar/etiquetar en el catálogo web).
    tipo_producto = serializers.CharField(
        source='tipo_producto.tipo_producto', read_only=True, default=None
    )
    descuento_porcentaje = serializers.SerializerMethodField()
    valor_con_descuento = serializers.SerializerMethodField()

    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'valor', 'image_principal', 'tipo_producto',
                  'numero_producto', 'creado_en', 'modificado_en',
                  'descuento_porcentaje', 'valor_con_descuento']

    def get_image_principal(self, obj):
        # Recorre en Python el prefetch 'imagenes' (evita el N+1 de .filter()).
        principal = next((img for img in obj.imagenes.all() if img.principal), None)
        return _abs_media(self, principal.imagen.url) if principal else None

    def get_descuento_porcentaje(self, obj):
        return _descuento_porcentaje_de(obj)

    def get_valor_con_descuento(self, obj):
        return _valor_con_descuento_de(obj)



class CatalogoProductRetrieveSerializer(serializers.ModelSerializer):
    imagenes = ProductImageSerializer(many=True, read_only=True)
    descuento_porcentaje = serializers.SerializerMethodField()
    valor_con_descuento = serializers.SerializerMethodField()

    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'valor', 'imagenes', 'numero_producto', 'detalles', 'tipo_producto','creado_en','modificado_en',
                  'descuento_porcentaje', 'valor_con_descuento']

    def get_descuento_porcentaje(self, obj):
        return _descuento_porcentaje_de(obj)

    def get_valor_con_descuento(self, obj):
        return _valor_con_descuento_de(obj)

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
