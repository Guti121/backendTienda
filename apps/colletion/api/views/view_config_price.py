from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from rest_framework.generics import CreateAPIView,DestroyAPIView,RetrieveAPIView
from rest_framework import status
from django.http import Http404
from rest_framework.response import Response

from Tienda_Virtual.globalFunctions import company_owner
from apps.base.api.user.viewsPermissions import IsAdminOrCreator, isCreator
from apps.colletion.models import Config_ProductModel
from ..serializers.serializer_config import CreateParametrosSerializer, EliminacionParametrosSerializer, ListarParametrosSerializer

from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView 

#Configuración de parámetros: crear o actualizar (una por tienda).
class CreacionParametrosAPIView(CreateAPIView):
    serializer_class = CreateParametrosSerializer
    permission_classes = [IsAuthenticated, isCreator]
    authentication_classes = [JWTAuthentication]

    def create(self, request, *args, **kwargs):
        """Upsert: si la tienda no tiene config la crea (201); si ya tiene, la
        actualiza (200). Antes rechazaba con 400 si ya existía y no había forma
        de editarla."""
        company = company_owner(self.request.user)
        instance = Config_ProductModel.objects.filter(tienda=company).first()

        serializer = self.get_serializer(
            instance, data=request.data, partial=bool(instance)
        )
        serializer.is_valid(raise_exception=True)

        if instance:
            serializer.save(modificado_por=self.request.user)
            return Response({'message': 'Parámetros actualizados.'},
                            status=status.HTTP_200_OK)

        serializer.save(creado_por=self.request.user, tienda=company)
        return Response({'message': 'Parámetros creados con éxito!'},
                        status=status.HTTP_201_CREATED)
    
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

        # `isCreator` + el filtro por tienda de get_queryset ya acotan quién puede
        # borrar; no hace falta un check extra por `creado_por` (que además
        # rompía si el creador de la tienda cambiaba).
        self.perform_destroy(instance)
        return Response({"message": "Parámetro eliminado exitosamente."}, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.delete()

class ConfigProductoRetrieveAPIView(RetrieveAPIView):
    serializer_class = ListarParametrosSerializer
    # Lectura: creator y admin (el admin usa el calculador y necesita ver la
    # config). Crear/borrar siguen siendo solo del creator.
    permission_classes = [IsAuthenticated, IsAdminOrCreator]
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
        # Acepta entero, decimal o string numérico; rechaza texto, booleanos y <= 0.
        raw = request.data.get('valor_mayor')
        try:
            valor_mayor = int(Decimal(str(raw)))
        except (TypeError, ValueError, InvalidOperation):
            return Response({'error': 'Debes ingresar un monto valido'}, status=status.HTTP_400_BAD_REQUEST)
        if valor_mayor <= 0:
            return Response({'error': 'El Valor Coste debe ser mayor que 0.'}, status=status.HTTP_400_BAD_REQUEST)

        company= company_owner(self.request.user)

        datos = Config_ProductModel.objects.filter(disponible=True, tienda=company).first()  # Cambia si necesitas filtrar de otra manera
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
        """Devuelve el margen como ratio (30 -> 0.30). El del body manda; si no,
        el de la config. `None` si no hay ninguno válido (el caller responde 400,
        no revienta)."""
        raw = request.data.get('margen')
        if raw not in (None, '', 0, '0'):
            try:
                m = Decimal(str(raw))
            except InvalidOperation:
                return None
            if m < 0 or m > 999:
                return None
            return m / 100
        if datos.margen_ganancia:
            return datos.margen_ganancia / 100
        return None

    def calculo_precio_sugerido(self, margen_ganancia, costos_fijos, unidades_proyectadas, valor_mayor):
        costo_fijo_u = Decimal(costos_fijos) / Decimal(unidades_proyectadas)
        costo_variable = Decimal(valor_mayor) + costo_fijo_u
        precio_unidad = costo_variable * (1 + Decimal(margen_ganancia))

        # Precios en pesos enteros.
        entero = lambda v: v.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return Response({
            'Precio_sugerido_Unidad': entero(precio_unidad),
            'ValorXmayor_CF': entero(costo_variable),
            'Margen': margen_ganancia
        }, status=status.HTTP_200_OK)