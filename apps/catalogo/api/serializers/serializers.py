


from rest_framework import serializers

from apps.colletion.models import ProductModel, TypeProductModel


class CatalogoProductListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'valor', 'image', 'numero_producto','creado_en', 'modificado_en']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        if request and instance.image:
            representation['image'] = request.build_absolute_uri(instance.image.url)
        return representation



class CatalogoProductRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'valor', 'image', 'numero_producto','detalles', 'tipo_producto']

       
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        if request and instance.image:
            representation['image'] = request.build_absolute_uri(instance.image.url)
        
        
        # Mostrar solo el nombre del tipo de producto
        if instance.tipo_producto:
            representation['tipo_producto'] = instance.tipo_producto.tipo_producto 

        return representation


class CatalogoTipoProductListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeProductModel
        fields = ['id','tipo_producto']
