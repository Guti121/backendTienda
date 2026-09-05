from django.http import Http404
from apps.base.models import UserProfile


def _perfil(user):
    """Devuelve el UserProfile del usuario.

    Usa el accesor OneToOne `user.profile`, que Django cachea en la instancia
    tras el primer acceso: si una vista llama varias veces a company_owner() /
    profile_user() en la misma request, solo se hace UNA consulta.
    """
    try:
        return user.profile
    except (UserProfile.DoesNotExist, AttributeError):
        raise Http404("El usuario no tiene un perfil asociado.")


def company_owner(user):
    return _perfil(user).company


def profile_user(user):
    return _perfil(user).tipo_usuario or None
