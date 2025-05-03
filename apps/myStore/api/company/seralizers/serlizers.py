


from rest_framework import serializers
from apps.myStore.models import Company

# Serializador con validaciones
class CreateCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'

    def validate_nit(self, value):
        """ Verificar que el NIT no exista """
        if Company.objects.filter(nit=value).exists():
            raise serializers.ValidationError("El NIT ya está registrado.")
        return value

    def validate_email(self, value):
        """ Verificar que el correo no esté registrado """
        if Company.objects.filter(email=value).exists():
            raise serializers.ValidationError("El correo ya está registrado.")
        return value

class RetrieveCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields =  ['url_logo', 'nit','company', 'name', 'phone', 'email', 'direction', 'municipality','creator_user']  # Corrige `direction` si aplica
        read_only_fields = fields  # Opcion


class UpdateCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company  # Asegúrate de incluir el modelo
        fields = ['url_logo', 'nit', 'company', 'name', 'phone', 'email', 'direction', 'municipality']
