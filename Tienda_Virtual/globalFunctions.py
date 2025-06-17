from django.shortcuts import get_object_or_404
from apps.base.models import UserProfile

def company_owner(user):
    user_profile = get_object_or_404(UserProfile, user=user)  # Obtiene el perfil del usuario
    return user_profile.company if user_profile.company else None  

def profile_user(user):
    user_profile = get_object_or_404(UserProfile, user=user)  # Obtiene el perfil del usuario
    return user_profile.tipo_usuario if user_profile.tipo_usuario else None  