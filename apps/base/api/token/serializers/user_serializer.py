# apps/base/api/serializers/user_serializer.py
from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.core.exceptions import ValidationError

from apps.base.models import TipoUsuario, UserProfile


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_verify = serializers.CharField(write_only=True)  # Agregamos el campo para verificar la contraseña

    class Meta:
        model = get_user_model()  # Usar el modelo de usuario personalizado si es necesario
        fields = ('username', "last_name","first_name",'email', 'password', 'password_verify')

    def validate(self, data):
        """Verifica que las contraseñas coincidan antes de crear el usuario."""
        if data['password'] != data['password_verify']:
            raise serializers.ValidationError({"password_verify": "Las contraseñas no coinciden."})
        return data

    def create(self, validated_data):
        """Eliminamos 'password_verify' antes de crear el usuario, ya que no es parte del modelo."""
        validated_data.pop('password_verify')  
        user = get_user_model().objects.create_user(**validated_data)

        # Crear un perfil de usuario con tipo 'cliente' por defecto
        UserProfile.objects.create(user=user, tipo_usuario=TipoUsuario.CLIENTE)

        return user
    