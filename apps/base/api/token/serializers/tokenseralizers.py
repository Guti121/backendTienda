from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(label=_("email"), write_only=True)
    password = serializers.CharField(
        label=_("password"),
        style={'input_type': 'password'},
        trim_whitespace=False,
        write_only=True
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError(_("Must include 'email' and 'password'."), code='authorization')

        user = authenticate(request=self.context.get('request'), email=email, password=password)

        if not user:
            raise serializers.ValidationError(_("Unable to log in with provided credentials."), code='authorization')

        token = super().get_token(user)  # Generar tokens JWT

        # Acceder al tipo de usuario desde UserProfile (si existe)
        profile = getattr(user, 'profile', None)  # Obtiene el perfil o None si no existe
        if not profile:
            raise serializers.ValidationError(_("Tipo de usuario desconocido."), code='authorization')
        tipo_usuario = getattr(profile, 'tipo_usuario', 'Desconocido')  # Obtiene el tipo o 'Desconocido'

        return {
            "access": str(token.access_token),
            "refresh": str(token),
            "user": {
                "email": user.email,
                "username": user.username,  # Si aún tienes username en el modelo, puedes mantenerlo
                "typeUser": tipo_usuario
            }
        }
