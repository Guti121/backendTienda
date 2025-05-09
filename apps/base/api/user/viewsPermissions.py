from rest_framework.permissions import BasePermission
##Permisos para asceder a las vistas

##Vista solo es de creador
class isCreator(BasePermission):
    message = "No tienes permiso para realizar esta acción."
    def has_permission(self, request, view):

        # Obtener el tipo de usuario de manera segura
        tipo_usuario = getattr(request.user, 'profile', None)
        if not tipo_usuario:
            return False  # Si no tiene perfil, no tiene permiso
        
        return request.user.is_authenticated and request.user.profile.tipo_usuario == "creator" and request.user.is_active

##Solo trabajador
class isWorker(BasePermission):
    message = "No tienes permiso para realizar esta acción."
    def has_permission(self, request, view):

        # Obtener el tipo de usuario de manera segura
        tipo_usuario = getattr(request.user, 'profile', None)
        if not tipo_usuario:
            return False  # Si no tiene perfil, no tiene permiso
        
        return request.user.is_authenticated and request.user.profile.tipo_usuario == "worker" and request.user.is_active

##Solo Admin
class isAdmin(BasePermission):
    message = "No tienes permiso para realizar esta acción."
    def has_permission(self, request, view):
        
        # Obtener el tipo de usuario de manera segura
        tipo_usuario = getattr(request.user, 'profile', None)
        if not tipo_usuario:
            return False  # Si no tiene perfil, no tiene permiso
        return request.user.is_authenticated and request.user.profile.tipo_usuario == "admin" and request.user.is_active

## trabajador y creador 
class IsWorkerOrCreator(BasePermission):
    """
    Permiso que permite acceso a 'worker' o 'creator'.
    """
    message = "No tienes permiso para realizar esta acción."

    def has_permission(self, request, view):
        
        # Obtener el tipo de usuario de manera segura
        tipo_usuario = getattr(request.user, 'profile', None)
        if not tipo_usuario:
            return False  # Si no tiene perfil, no tiene permiso
        return request.user.is_authenticated and request.user.is_active and request.user.profile.tipo_usuario in ["worker", "creator","admin"]

## admin y creador 
class IsAdminOrCreator(BasePermission):
    """
    Permiso que permite acceso a 'worker' o 'creator'.
    """
    message = "No tienes permiso para realizar esta acción."

    def has_permission(self, request, view):
        
        # Obtener el tipo de usuario de manera segura
        tipo_usuario = getattr(request.user, 'profile', None)
        if not tipo_usuario:
            return False  # Si no tiene perfil, no tiene permiso
        
        return request.user.is_authenticated and request.user.is_active and request.user.profile.tipo_usuario in ["creator","admin"]



