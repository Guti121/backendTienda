
import logging
from datetime import datetime
from decimal import Decimal
from django.forms import ValidationError
from rest_framework.generics import CreateAPIView, DestroyAPIView,ListAPIView,RetrieveAPIView
from rest_framework import serializers  
from Tienda_Virtual.globalFunctions import company_owner
from apps.shoppingcart.models import Factura, FacturaDetalle
from apps.base.api.user.viewsPermissions import IsAdminOrCreator, IsWorkerOrCreator, isCreator
from apps.colletion.models import ProductModel
from .serializers.serializers import FacturaListSerializer, FacturaSerializer,FacturaCreateSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import PermissionDenied
from django.db import transaction
from rest_framework.response import Response
from rest_framework import status
from django.utils.dateparse import parse_date
from django.utils import timezone
from babel.numbers import format_currency
from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
from collections import defaultdict

logger = logging.getLogger(__name__)


class FacturasCreateView(CreateAPIView):
    serializer_class = FacturaCreateSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsWorkerOrCreator]

    def get_queryset(self):
        company=company_owner(self.request.user)
        return Factura.objects.filter(tienda = company)

    def perform_create(self, serializer):

        company = company_owner(self.request.user)

        detalles = serializer.validated_data.get('detalles')
        if not detalles:  # Si no envían detalles
            raise ValueError('Carrito Vacio')

        # Agrupar cantidades por producto (por si el mismo producto viene en
        # varias líneas del carrito).
        productos_a_procesar = defaultdict(int)
        for detalle in detalles:
            productos_a_procesar[detalle['producto'].id] += detalle['cantidad']

        # Verificación de stock, descuento y creación de la factura dentro de una
        # sola transacción. `select_for_update()` bloquea las filas de producto
        # hasta el commit, de modo que dos ventas simultáneas del mismo producto
        # no puedan dejar el stock negativo (sobreventa).
        with transaction.atomic():
            productos = {
                p.id: p
                for p in ProductModel.objects
                    .select_for_update()
                    .filter(id__in=productos_a_procesar.keys(), tienda=company)
            }

            for producto_id, cantidad_solicitada in productos_a_procesar.items():
                producto = productos.get(producto_id)
                if producto is None:
                    raise ProductModel.DoesNotExist(
                        f"Producto {producto_id} no encontrado en esta tienda."
                    )
                if not producto.disponible or producto.unidades_disponibles < cantidad_solicitada:
                    raise serializers.ValidationError({
                        "error": "No hay suficiente stock para el producto ",
                        "producto_nombre": producto.nombre,
                        "stock": producto.unidades_disponibles,
                        "producto_id": producto_id,
                    })

            for producto_id, cantidad_solicitada in productos_a_procesar.items():
                producto = productos[producto_id]
                producto.unidades_disponibles -= cantidad_solicitada
                if producto.unidades_disponibles == 0:
                    producto.disponible = False

            # bulk_update evita llamar a ProductModel.save() por cada producto
            # (que regeneraría códigos de barras); solo tocamos las columnas de stock.
            ProductModel.objects.bulk_update(
                productos.values(), ['unidades_disponibles', 'disponible']
            )

            serializer.save(creado_por=self.request.user, tienda=company)
            
    def post(self, request, *args, **kwargs):
            serializer = self.get_serializer(data=request.data)
            try:
                serializer.is_valid(raise_exception=True)  # Maneja automáticamente los errores de validación
                self.perform_create(serializer)  # Lógica personalizada para verificar permisos

                 # Obtener el ID de la factura creada
                factura_id = serializer.instance.id

                return Response({
                    'mensaje': 'Facturado de manera exitosa',
                    'factura_id': factura_id,  # Aquí devolvemos el ID de la factura
                    'Factura': serializer.data
                }, status=status.HTTP_201_CREATED)
            
            except serializers.ValidationError as e:
                return Response({"error": e.detail}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError as e:
                return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except PermissionDenied as e:
                return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
            except ProductModel.DoesNotExist as e:
                return Response({"error": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                # Captura cualquier otro error inesperado
                return Response(
                    {"error": "Ocurrió un error inesperado.", "detalle": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )


 # Para listar todas las facturas con sus detalles

class FacturasListView(ListAPIView):
    queryset = Factura.objects.all()
    serializer_class = FacturaListSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsAdminOrCreator]

    def get_queryset(self):
        company=company_owner(self.request.user)
        queryset = Factura.objects.filter(tienda=company)

        # Obtener el queryset filtrado
        # Obtener parámetros de la solicitud
        month = self.request.query_params.get('month', None)
        year = self.request.query_params.get('year', None)
        date_str = self.request.query_params.get('date', None)

        # Filtrar por mes y año si se pasan ambos parámetros
        if month and year:
            queryset = queryset.filter(fecha__year=year, fecha__month=month)
            return queryset
        
        # Filtrar por fecha específica si se pasa el parámetro 'date'
        elif date_str:
            try:
                # Validar formato
                year, month, day = map(int, date_str.split('-'))
                if not (1 <= month <= 12 and 1 <= day <= 31):
                    raise ValueError("Fecha fuera de rango")

                date_parse = datetime.strptime(date_str, "%Y-%m-%d").date()
                return queryset.filter(fecha__date=date_parse)

            except (ValueError, TypeError):
                return queryset.none()  # Evita error 500 y solo devuelve una lista vacía
        else:
            current_date = timezone.now()
            queryset = queryset.filter(fecha__year=current_date.year, fecha__month=current_date.month)
            return queryset
            

        

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        # Nº de facturas y suma de 'total' se calculan SIN join (si se pusiera
        # Sum('detalles__cantidad') en el mismo aggregate, el join inflaría el
        # total repitiendo cada factura por cada detalle).
        resumen = queryset.aggregate(
            numero=Count('id'),
            total=Coalesce(Sum('total'), Decimal('0.00')),
        )
        total_cantidad = queryset.aggregate(
            c=Coalesce(Sum('detalles__cantidad'), 0)
        )['c']

        return Response({
            'numero_de_facturas': resumen['numero'],
            'total_cantidad_de_procuctos': total_cantidad,
            'total_facturas': format_currency(resumen['total'], 'COP', locale='es_CO'),
            'facturas': serializer.data,
        }, status=status.HTTP_200_OK)



# Para obtener una sola factura con sus detalles
class FacturasDetailView(RetrieveAPIView):
    
    serializer_class = FacturaSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsWorkerOrCreator]  # Asegura que el usuario esté autenticado

    def get_queryset(self):
        company=company_owner(self.request.user)
        return (Factura.objects
                .filter(tienda=company)
                .select_related('creado_por', 'tienda')
                .prefetch_related('detalles__producto'))

    def get(self, request, *args, **kwargs):
             return super().get(request, *args, **kwargs)

class FacturaDestroyView(DestroyAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsAdminOrCreator]

    def get_queryset(self):
        company = company_owner(self.request.user)
        return Factura.objects.filter(tienda=company)


    def perform_destroy(self, instance):
  
        # Llama al método de eliminación del modelo
        pk = instance.id
        company=company_owner(self.request.user)
        factura_detalles = FacturaDetalle.objects.filter(tienda=company, factura=pk)

        for detalle in factura_detalles:
            producto = detalle.producto
            cantidad = detalle.cantidad

            if producto:  # ✅ Verifica que el producto aún exista
                try:
                    producto.unidades_disponibles += cantidad
                    if producto.unidades_disponibles != 0:
                        producto.disponible = True
                    producto.save()
                except Exception:
                    logger.exception("Error al reponer stock del producto %s", producto.id)
    
        instance.delete()

    def delete(self, request, *args, **kwargs):
    
        instance = self.get_object()  # Obtiene la factura a eliminar
        self.perform_destroy(instance)  # Llama a perform_destroy
        return Response({"message": "Factura eliminada con éxito."},status=status.HTTP_204_NO_CONTENT)

