
from django.db.models import Q
from rest_framework.generics import CreateAPIView,RetrieveAPIView,UpdateAPIView,ListAPIView
from django.shortcuts import get_object_or_404
from apps.base.api.user.serializers import ListUserProfileSerializer
from Tienda_Virtual.globalFunctions import company_owner
from apps.base.models import TipoUsuario, UserProfile
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from apps.base.api.user.viewsPermissions import IsAdminOrCreator
from rest_framework import status
from rest_framework.response import Response

#Esta vista solo lo podra ver el creador y el admin 
#Se listara los usuarios asociados a una empresa 

class ListUserCompanyAPIView(ListAPIView):
    serializer_class = ListUserProfileSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]

    def get_queryset(self):
        company = company_owner(self.request.user)
        if not company:
            return UserProfile.objects.none()  # Retorna una queryset vacía si no hay empresa
        
        return UserProfile.objects.filter(company=company).exclude(
            Q(user=self.request.user) | Q(tipo_usuario=TipoUsuario.CREATOR)
        ).select_related('company')

#Se realiza esta vista para eliminar los usuarios que pertenecen a la compañia
class UpdateUserCompanyAPIView(UpdateAPIView):
    serializer_class = ListUserProfileSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]

    def get_queryset(self):
        """ Devuelve solo los usuarios de la misma empresa que el usuario autenticado """
        company = company_owner(self.request.user)
        return UserProfile.objects.filter(company=company)

    def patch(self, request, *args, **kwargs):
        pk = kwargs.get('pk')  # Captura el ID del usuario a actualizar
        user_to_update = self.get_queryset().filter(pk=pk).first()  # Busca dentro de la empresa

        if not user_to_update:
            return Response({"error": "Usuario no encontrado o no tienes permiso para actualizarlo"}, status=status.HTTP_404_NOT_FOUND)

        # Actualiza los campos
        user_to_update.tipo_usuario = TipoUsuario.CLIENTE
        user_to_update.company = None
        user_to_update.save()

        return Response({"message": "Usuario actualizado correctamente"}, status=status.HTTP_200_OK)