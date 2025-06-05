
from datetime import datetime
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
from rest_framework.response import Response
from rest_framework import status
from django.utils.dateparse import parse_date
from django.utils import timezone
from babel.numbers import format_currency
from django.db.models import Sum, F,DecimalField,ExpressionWrapper
from django.db.models.functions import Coalesce
from collections import defaultdict

class FacturasCreateView(CreateAPIView):
    serializer_class = FacturaCreateSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsWorkerOrCreator]

    def get_queryset(self):
        company=company_owner(self.request.user)
        return Factura.objects.filter(tienda = company)

    def perform_create(self, serializer):
        
        company=company_owner(self.request.user)


        # Obtener los detalles de la factura para verificar el stock
        detalles = serializer.validated_data.get('detalles')
        if not detalles:  # Si no envían detalles
                raise  ValueError('Carrito Vacio')
        # Agrupar cantidades por producto
        productos_a_procesar = defaultdict(int)

        for detalle in detalles:
            producto = detalle['producto']  # ID del producto
            producto_id = producto.id
            cantidad = detalle['cantidad']  # Cantidad solicitada
            productos_a_procesar[producto_id] += cantidad  # Sumar cantidades por producto

        # Verificar que todos los productos tienen el stock suficiente
        for producto_id, cantidad_solicitada in productos_a_procesar.items():
            producto = ProductModel.objects.get(id=producto_id, tienda = company)  # Obtén el producto desde la base de datos

            # Verificar si hay stock suficiente
            if producto.unidades_disponibles < cantidad_solicitada or not producto.disponible:
                raise serializers.ValidationError({
                    "error":"No hay suficiente stock para el producto ",
                    "producto_nombre":producto.nombre,
                    "stock":producto.unidades_disponibles,
                    "producto_id":producto_id
                    }
                )

        # Si todos los productos tienen el stock suficiente, proceder a descontar
        for producto_id, cantidad_solicitada in productos_a_procesar.items():
            producto = ProductModel.objects.get(id=producto_id,tienda = company)  # Obtener nuevamente el producto

            # Realizar el descuento de unidades
            producto.unidades_disponibles -= cantidad_solicitada
            if producto.unidades_disponibles == 0:
                producto.disponible = False

            producto.save()

        # Finalmente, guarda el objeto de la factura
        
        # Creamos la instancia pero aún no guardamos
        
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
                return Response({"error": e.detail}, status=status.HTTP_404_NOT_FOUND)
            except ValueError as e:
                return Response({"error":str(e)}, status=status.HTTP_404_NOT_FOUND)
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
        print(month,'este es el valor de month')
        year = self.request.query_params.get('year', None)
        print(year,'este es el valor de year')
        date_str = self.request.query_params.get('date', None)
        print(date_str,'este es el valor de date')
        
       
        # Filtrar por mes y año si se pasan ambos parámetros
        if month and year:
            print(month)
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
            print('entre else')
            current_date = timezone.now()
            print('current',current_date)
            queryset = queryset.filter(fecha__year=current_date.year, fecha__month=current_date.month)
            return queryset
            

        

    def list(self, request, *args, **kwargs):
        # Obtener el queryset filtrado
        queryset = self.get_queryset()

        # Calcular el total de las facturas
        

        # Serializar los datos
        serializer = self.get_serializer(queryset, many=True)
        print(queryset.values('total'))  # Esto mostrará los valores de `total` antes de la agregación.

        
        totales = queryset.aggregate(
            total_cantidad=Coalesce(Sum(F('detalles__cantidad')), 0),
            total_x_mayor=Coalesce(Sum(ExpressionWrapper(
                F('detalles__producto__valor_mayor') * F('detalles__cantidad'),
                output_field=DecimalField()
            )),0, output_field=DecimalField()),
            total_x_mayor_cf=Coalesce(Sum(ExpressionWrapper(
                F('detalles__producto__valor_costos_fijos') * F('detalles__cantidad'),
                output_field=DecimalField()
            )),0, output_field=DecimalField())
        )
        print(totales)
        total_facturas,ganancia,ganancia_cf=self.total_facturas(queryset,totales['total_x_mayor'],totales['total_x_mayor_cf'])
        
        total_facturas_cop = format_currency(total_facturas, 'COP', locale='es_CO')
        """
        total_x_mayor_cop = format_currency(totales['total_x_mayor'], 'COP', locale='es_CO')
        total_x_mayor_cf_cop = format_currency(totales['total_x_mayor_cf'],'COP',locale='es_CO')
        total_ganancia_cop = format_currency(ganancia, 'COP', locale='es_CO')
        total_ganancia_cf_cop = format_currency(ganancia_cf, 'COP', locale='es_CO')
        total_solo_cf=format_currency(ganancia-ganancia_cf,'COP', locale='es_CO')

        'Total precio x mayor':total_x_mayor_cop,
            'Total precio x mayor cf':total_x_mayor_cf_cop,
            'Total Ganancia sin CF':total_ganancia_cop,
            'Total Ganancia cf':total_ganancia_cf_cop,
            'Total Cfs cubierto':total_solo_cf,"""
        # Devolver la respuesta con el total y las facturas serializadas
        return Response({
            'numero_de_facturas': len(queryset),
            
            'total_cantidad_de_procuctos':totales['total_cantidad'],
            'total_facturas': total_facturas_cop,
            


            'facturas': serializer.data
        }, status=status.HTTP_200_OK)

    def total_facturas(self,queryset,x_mayor,x_mayor_cf):
        total=0.0
        ganancia=0.0

        for factura in queryset:
            total+=float(factura.total)
        print('total',total)
        ganancia=float(total)-float(x_mayor)
        print('total',total)
        ganancia_cf=float(total)-float(x_mayor_cf)
        
        
        return total,ganancia,ganancia_cf
    


# Para obtener una sola factura con sus detalles
class FacturasDetailView(RetrieveAPIView):
    
    serializer_class = FacturaSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsWorkerOrCreator]  # Asegura que el usuario esté autenticado

    def get_queryset(self):
        company=company_owner(self.request.user)
        queryset = Factura.objects.filter(tienda=company)
        return queryset
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
                except Exception as e:
                    print(f"Error al actualizar producto {producto.id}: {str(e)}")
    
        instance.delete()

    def delete(self, request, *args, **kwargs):
    
        instance = self.get_object()  # Obtiene la factura a eliminar
        self.perform_destroy(instance)  # Llama a perform_destroy
        return Response({"message": "Factura eliminada con éxito."},status=status.HTTP_204_NO_CONTENT)

