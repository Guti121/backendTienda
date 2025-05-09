

from rest_framework import serializers
from apps.colletion.models import Config_ProductModel


class CreateParametrosSerializer(serializers.ModelSerializer):   
    class Meta:
        model=Config_ProductModel
        fields='__all__'

        def validate(self,data):
            if not data.get('costos_fijos'):
                 raise serializers.ValidationError("El campo 'costos_fijos' es requerido.")
            

        def create(self,validated_data):
            
            configuraciones=Config_ProductModel.objects.create(**validated_data)

            return configuraciones
        
class EliminacionParametrosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config_ProductModel
        fields = ['id']  # Corregido el nombre del campo

class ListarParametrosSerializer(serializers.ModelSerializer):
    class Meta:
        model= Config_ProductModel
        fields='__all__'