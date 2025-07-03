


from rest_framework import serializers

from apps.colletion.models import ProductModel, TypeProductModel


class CatalogoProductListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'valor', 'image', 'numero_producto']

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
        return representation


class CatalogoTipoProductListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeProductModel
        fields = ['id','tipo_producto']
