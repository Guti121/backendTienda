from rest_framework.permissions import BasePermission


class IsCompanyMember(BasePermission):
    """
    Permite el acceso solo a los usuarios que pertenecen a la empresa del producto.
    """

    def has_object_permission(self, request, view, obj):
        
        # Verifica si el usuario pertenece a la misma empresa que el producto
        return request.user.profile.company.id == obj.tienda