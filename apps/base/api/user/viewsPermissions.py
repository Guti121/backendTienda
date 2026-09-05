from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    """Concede acceso si el usuario está autenticado, activo y su
    `profile.tipo_usuario` está en `allowed_roles`.

    Las clases de abajo son solo la lista de roles permitida; antes cada una
    repetía el mismo bloque de comprobaciones.
    """
    message = "No tienes permiso para realizar esta acción."
    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and user.is_active):
            return False
        profile = getattr(user, "profile", None)
        return profile is not None and profile.tipo_usuario in self.allowed_roles


class isCreator(RolePermission):
    allowed_roles = ("creator",)


class isWorker(RolePermission):
    allowed_roles = ("worker",)


class isAdmin(RolePermission):
    allowed_roles = ("admin",)


class IsWorkerOrCreator(RolePermission):
    """worker, creator o admin."""
    allowed_roles = ("worker", "creator", "admin")


class IsAdminOrCreator(RolePermission):
    """creator o admin."""
    allowed_roles = ("creator", "admin")
