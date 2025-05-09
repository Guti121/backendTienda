

from rest_framework import serializers
from apps.base.models import UserProfile



class ListUserProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.first_name", read_only=True)  
    last_name = serializers.CharField(source="user.last_name", read_only=True)  
    email = serializers.CharField(source="user.email", read_only=True)  
    company= serializers.CharField(source="company.name", read_only=True)
    class Meta:
        model = UserProfile
        fields = ['id','name', 'last_name', 'email', 'company', 'tipo_usuario']  # Corrección de 'Last_name' a 'last_name'
