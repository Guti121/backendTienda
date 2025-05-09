from apps.colletion.models import Bar_codeModel
from rest_framework import serializers


class BarCodeSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source='product.nombre')

    class Meta:
        model = Bar_codeModel
        fields = ['nombre', 'barcode']
