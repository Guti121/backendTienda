from rest_framework.exceptions import NotFound,PermissionDenied
from django.db import transaction
from rest_framework.generics import CreateAPIView,RetrieveAPIView,DestroyAPIView,UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from apps.myStore.models import Company
from apps.base.models import TipoUsuario, UserProfile
from Tienda_Virtual.globalFunctions import company_owner
from apps.myStore.api.company.seralizers.serlizers import CreateCompanySerializer, RetrieveCompanySerializer, UpdateCompanySerializer
from apps.base.api.user.viewsPermissions import IsAdminOrCreator, IsWorkerOrCreator, isCreator, isWorker
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import status
from rest_framework.generics import UpdateAPIView


#Esta vistas se encarga de crear la compañia 
#asegurandose que el usuario no pertenezca a ninguna compañia 
#Tambien verificamos que el tipo de usuario sea cliente , para asi poder crearlo 
class CompanyCreateAPIView(CreateAPIView):
    serializer_class = CreateCompanySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        if not hasattr(user, 'profile'):  # Verifica si el perfil existe
            return Response({'error': 'No tienes definido el tipo de usuario!!'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            user_profile = user.profile  # Ahora sí es seguro acceder al perfil
        # Verificar si el usuario ya pertenece a una empresa
        if company_owner(user):  
            return Response({'error': 'Ya haces parte de una compañía!!'}, status=status.HTTP_400_BAD_REQUEST)

        # Validar que el usuario sea CLIENTE antes de crear la empresa
        if user_profile.tipo_usuario != TipoUsuario.CLIENTE:
            return Response({'error': 'Es posible que estes vinculado a una compañia.'}, status=status.HTTP_403_FORBIDDEN)
        

        # Crear la empresa; el creador se fija desde el usuario autenticado
        # (creator_user es read_only en el serializer).
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            company = serializer.save(creator_user=user)

            # Actualizar el perfil del usuario: cambiar a "creator" y vincular la empresa
            user_profile.tipo_usuario = TipoUsuario.CREATOR
            user_profile.company = company
            user_profile.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


#Se realiza un Vista para listar los datos de la compañia perteneciente al usuario,
#Dicha vista prodra adseder solo los usuarios pertenicientes a esta compañia


class CompanyRetrieveAPIView(RetrieveAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsWorkerOrCreator]
    serializer_class = RetrieveCompanySerializer

    def get_object(self):
        """Devuelve la compañía del usuario autenticado sin necesidad de un `pk` en la URL."""
        user = self.request.user
        company = company_owner(user)  # Debe devolver una instancia de `Company`

        if not company:
            raise NotFound("No tienes una empresa asociada.")

        return company


#Se crea una vista para eliminar una compañia 
#para esto se verifica, que cuando se elimine el usuario pase a ser cliente de nuevo
class CompanyDestroyAPIView(DestroyAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, isCreator]

    def delete(self, request, *args, **kwargs):
        user = request.user

        if not hasattr(user, 'profile'):
            return Response({'error': 'No tienes definido el tipo de usuario!!'}, status=status.HTTP_400_BAD_REQUEST)

        user_profile = user.profile  # Perfil del usuario que hace la petición
        
        if user_profile.tipo_usuario != TipoUsuario.CREATOR:
            return Response({'error': 'No eres el propietario de esta compañía.'}, status=status.HTTP_403_FORBIDDEN)

        # Verificar si el usuario es dueño de la empresa
        company = company_owner(user)

        if not company:
            return Response({'error': 'No tienes una compañía asociada.'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():  # Asegurar que ambas acciones ocurran juntas
            # Cambiar a todos los usuarios de la empresa a tipo CLIENTE
            updated_count = UserProfile.objects.filter(company=company).update(tipo_usuario=TipoUsuario.CLIENTE, company=None)
            
            if updated_count == 0:
                return Response({'warning': 'No se encontraron usuarios para actualizar.'}, status=status.HTTP_200_OK)

            # Eliminar la empresa
            company.delete()

        return Response({'message': 'Compañía eliminada y usuarios actualizados correctamente.'}, status=status.HTTP_204_NO_CONTENT)
    

class CompanyUpdateAPIView(UpdateAPIView):
    serializer_class = UpdateCompanySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,isCreator]

    def get_object(self):
        """Obtiene la compañía asociada al usuario autenticado."""
        user = self.request.user
        company = company_owner(user)
        if not company:
            raise NotFound("No tienes una empresa asociada.")
        return company

    def patch(self, request, *args, **kwargs):
        company = self.get_object()
        
        # Filtrar solo los campos permitidos
        allowed_fields = {'url_logo', 'nit', 'company', 'name', 'phone', 'email', 'direction', 'municipality'}
        data = {key: value for key, value in request.data.items() if key in allowed_fields}

        if not data:
            return Response({'error': 'No hay campos válidos para actualizar.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(company, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

