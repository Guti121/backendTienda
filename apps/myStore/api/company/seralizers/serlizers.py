


from rest_framework import serializers
from apps.myStore.models import Company

# Serializador con validaciones
class CreateCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'url_logo', 'nit', 'company', 'name', 'phone',
                  'email', 'direction', 'municipality', 'creator_user']
        # El creador se toma del usuario autenticado en la vista, no del body.
        read_only_fields = ['id', 'creator_user']

    def validate_nit(self, value):
        """ Verificar que el NIT no exista """
        if Company.objects.filter(nit=value).exists():
            raise serializers.ValidationError("El NIT ya está registrado.")
        return value
    
    def validate_name(self, value):
        """ Verificar que el NIT no exista """
        if Company.objects.filter(name=value).exists():
            raise serializers.ValidationError("El nombre ya está registrado.")
        return value

    def validate_email(self, value):
        """ Verificar que el correo no esté registrado """
        if Company.objects.filter(email=value).exists():
            raise serializers.ValidationError("El correo ya está registrado.")
        return value

class RetrieveCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['url_logo', 'nit', 'company', 'name', 'phone', 'email',
                  'direction', 'municipality', 'creator_user',
                  # Personalización del catálogo público.
                  'catalog_font', 'catalog_tagline', 'catalog_announcement',
                  'catalog_banner']
        read_only_fields = fields  # Opcion


class UpdateCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company  # Asegúrate de incluir el modelo
        fields = ['url_logo', 'nit', 'company', 'name', 'phone', 'email',
                  'direction', 'municipality',
                  # Personalización del catálogo público.
                  'catalog_font', 'catalog_tagline', 'catalog_announcement',
                  'catalog_banner']
