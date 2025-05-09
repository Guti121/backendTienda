from decimal import Decimal
from logging import raiseExceptions
import string
from urllib import request
from rest_framework.generics import CreateAPIView,DestroyAPIView,RetrieveAPIView
from rest_framework import status
from django.http import Http404
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from Tienda_Virtual.globalFunctions import company_owner
from apps.base.api.user.viewsPermissions import IsAdminOrCreator, isCreator
from apps.colletion.models import Config_ProductModel
from ..serializers.serializer_config import CreateParametrosSerializer, EliminacionParametrosSerializer, ListarParametrosSerializer

from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView 

#Creacion de parametros de configuracion
class CreacionParametrosAPIView(CreateAPIView):
    serializer_class = CreateParametrosSerializer
    permission_classes = [IsAuthenticated, isCreator]
    authentication_classes = [JWTAuthentication]

    def perform_create(self, serializer):
        """Evita la creación de duplicados y asigna la empresa antes de guardar."""
        company = company_owner(self.request.user)  # Obtener la empresa del usuario
        
        # Verificar si ya existe un registro con esta tienda
        if Config_ProductModel.objects.filter(tienda=company).exists():
            raise ValidationError({"error": "Ya existen parámetros para esta tienda."})

        # Si no existe, proceder con la creación
        serializer.save(creado_por=self.request.user, tienda=company)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        self.perform_create(serializer)  # Llama a perform_create para validar y guardar

        return Response({'message': 'Parámetros creados con éxito!'}, status=status.HTTP_201_CREATED)
    
#Eliminar Parametros APIView
class EliminacionParametrosAPIView(DestroyAPIView):
    serializer_class = EliminacionParametrosSerializer
    permission_classes = [IsAuthenticated, isCreator]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        company = company_owner(self.request.user)
        return Config_ProductModel.objects.filter(tienda=company)

    def destroy(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        instance = queryset.first()  # Obtiene el primer registro disponible
        
        if not instance:
            return Response({"error": "No hay parámetros para eliminar."}, status=status.HTTP_404_NOT_FOUND)

        # Verificar si el usuario autenticado es el creador del objeto
        if instance.creado_por != request.user:
            return Response({"error": "No tienes permisos para eliminar este objeto."}, status=status.HTTP_403_FORBIDDEN)

        self.perform_destroy(instance)
        return Response({"message": "Parámetro eliminado exitosamente."}, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.delete()

class ConfigProductoRetrieveAPIView(RetrieveAPIView):
    serializer_class = ListarParametrosSerializer
    permission_classes = [IsAuthenticated,isCreator]
    authentication_classes = [JWTAuthentication]

    
    def get_queryset(self):
        # Retorna solo los productos donde disponible es True
        company= company_owner(self.request.user)
        return Config_ProductModel.objects.filter(disponible=True, tienda = company)

    def get_object(self):
        # Obtiene el primer objeto que coincide con el filtro
        queryset = self.get_queryset()
        obj = queryset.first()  # Obtiene el primer objeto disponible
        if obj is None:
            raise Http404("No se encontró ninguna configuracion disponible.")
        return obj

    def retrieve(self, request, *args, **kwargs):
        # Llama a get_object para obtener el objeto y luego serializarlo
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

#Retorna el precio sugerido haciendo el calculo junto con la funcion calculo_precio_sugerido
class PrecioSugeridoAPIView(APIView):
    permission_classes = [IsAuthenticated,IsAdminOrCreator]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        valor_mayor = request.data.get('valor_mayor')
        print(valor_mayor)
        if valor_mayor is None or not isinstance(valor_mayor, int):
            return Response({'error': 'Debes ingresar un monto valido'}, status=status.HTTP_400_BAD_REQUEST)

        company= company_owner(self.request.user)

        datos = Config_ProductModel.objects.filter(disponible=True, tienda=company).first()  # Cambia si necesitas filtrar de otra manera
        print(datos)
        if not datos:
            return Response({'error': 'Datos no encontrados'}, status=status.HTTP_404_NOT_FOUND)

        costos_fijos = datos.costos_fijos
        unidades_proyectadas = datos.promedio_productos_vendidos

        if unidades_proyectadas <= 0:
            return Response({'error': 'Unidades proyectadas debe ser mayor que cero'}, status=status.HTTP_400_BAD_REQUEST)

        margen_ganancia = self.obtener_margen_ganancia(datos, request)

        if margen_ganancia is None:
            return Response({'error': 'No se ha proporcionado un margen de ganancia válido.'}, status=status.HTTP_400_BAD_REQUEST)

        return self.calculo_precio_sugerido(margen_ganancia, costos_fijos, unidades_proyectadas, valor_mayor)

    def obtener_margen_ganancia(self, datos, request):
        if request.data.get('margen'):
            return Decimal(request.data.get('margen')) / 100
        elif datos.margen_ganancia is not None and datos.margen_ganancia != 0:
            return datos.margen_ganancia / 100
        return None

    def calculo_precio_sugerido(self, margen_ganancia, costos_fijos, unidades_proyectadas, valor_mayor):
        costo_fijo_u = Decimal(costos_fijos) / Decimal(unidades_proyectadas)     
        costo_variable = Decimal(valor_mayor) + costo_fijo_u
        precio_unidad = costo_variable * (1 + Decimal(margen_ganancia))

        return Response({
            'Precio_sugerido_Unidad': precio_unidad,
            'ValorXmayor_CF': costo_variable,
            'Margen': margen_ganancia
        }, status=status.HTTP_200_OK)