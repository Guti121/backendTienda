from rest_framework import serializers
from ...models import ProductModel,TypeProductModel


#.............................................................................
""".............Se realizan los serializadores para Product..........."""

class ProductModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductModel
        fields = '__all__'

    def validate(self, data):
        # Validación de campos requeridos
        required_fields = ['nombre', 'tipo_producto', 'detalles', 'valor', 'valor_mayor', 'unidades_disponibles']
        for field in required_fields:
            if not data.get(field):
                raise serializers.ValidationError({field: f"El campo '{field}' es requerido."})

        # Validar que el valor y el valor_mayor sean positivos
        if data.get('valor') <= 0:
            raise serializers.ValidationError({"valor": "El valor debe ser mayor a 0."})
        if data.get('valor_mayor') <= 0:
            raise serializers.ValidationError({"valor_mayor": "El valor mayor debe ser mayor a 0."})

        # Validar unidades disponibles
        if data.get('unidades_disponibles') < 0:
            raise serializers.ValidationError({"unidades_disponibles": "Las unidades disponibles no pueden ser negativas."})

        return data


#serializador para listFilter View
class ProductModelListFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductModel
        fields = ['id','image','nombre','tipo_producto','detalles','valor','unidades_disponibles','numero_producto']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Aquí cambiamos el campo 'categoria' de ID a 'nombre'
        category_name = instance.tipo_producto.tipo_producto  
        representation['tipo_producto'] = category_name
        
        return representation
##serializador para retrieve product
class ProductModelRetrieveProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductModel
        fields = ['id','image','nombre','tipo_producto','detalles','valor','unidades_disponibles','numero_producto']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Aquí cambiamos el campo 'categoria' de ID a 'nombre'
        category_name = instance.tipo_producto.tipo_producto  
        representation['tipo_producto'] = category_name
        
        return representation
    
class ProductModelRetrieveProductCreatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductModel
        fields = ['id','image','nombre','tipo_producto','detalles','valor','valor_mayor','valor_costos_fijos','unidades_disponibles','numero_producto']

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
    class Meta:
        model = ProductModel
        fields = ['unidades_disponibles']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Aquí cambiamos el campo 'categoria' de ID a 'nombre'
        category_name = instance.tipo_producto.tipo_producto  
        representation['tipo_producto'] = category_name
        
        return representation

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
