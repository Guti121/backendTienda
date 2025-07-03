

from apps.myStore.models import Company
from rest_framework import serializers

class CatalogoCompanySerializer(serializers.ModelSerializer):
    """
    Serializer for the Company model.
    """
    class Meta:
        model = Company
        fields = ['id', 'name', 'url_logo', 'phone', 'email', 'direction', 'municipality']
    
    