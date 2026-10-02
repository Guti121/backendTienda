
import logging
from datetime import datetime
from decimal import Decimal
from django.forms import ValidationError
from rest_framework.generics import CreateAPIView, DestroyAPIView,ListAPIView,RetrieveAPIView
from rest_framework import serializers  
from Tienda_Virtual.globalFunctions import company_owner
from Tienda_Virtual.dateutils import day_bounds, month_bounds
from apps.shoppingcart.models import CajaModel, Factura, FacturaDetalle
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

        caja_abierta = CajaModel.objects.filter(tienda=company, cerrada_en__isnull=True).first()
        if not caja_abierta:
            raise serializers.ValidationError(
                {"error": "No hay una caja abierta. Abrí caja antes de facturar."}
            )

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

            serializer.save(creado_por=self.request.user, tienda=company, caja=caja_abierta)
            
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
            except Exception:
                # No se filtra el detalle del error al cliente; queda en el log.
                logger.exception("Error inesperado creando factura")
                return Response(
                    {"error": "Ocurrió un error inesperado al crear la factura."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )


 # Para listar todas las facturas con sus detalles

class FacturasListView(ListAPIView):
    queryset = Factura.objects.all()
    serializer_class = FacturaListSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsAdminOrCreator]

    def get_queryset(self):
        company = company_owner(self.request.user)
        queryset = Factura.objects.filter(tienda=company)

        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')
        date_str = self.request.query_params.get('date')
        metodo_pago = self.request.query_params.get('metodo_pago')

        # Se filtra con rangos [inicio, fin) en vez de fecha__year/__month/__date:
        # esos lookups sobre DateTimeField con USE_TZ se traducen a CONVERT_TZ y
        # necesitan las tablas de timezone de MySQL cargadas; si faltan devuelven
        # NULL y no matchea nada. El rango explícito no depende de eso y usa índice.
        if month and year:
            try:
                inicio, fin = month_bounds(int(year), int(month))
            except (ValueError, TypeError):
                return queryset.none()
            queryset = queryset.filter(fecha__gte=inicio, fecha__lt=fin)
        elif date_str:
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return queryset.none()
            inicio, fin = day_bounds(d)
            queryset = queryset.filter(fecha__gte=inicio, fecha__lt=fin)
        else:
            hoy = timezone.localtime(timezone.now())
            inicio, fin = month_bounds(hoy.year, hoy.month)
            queryset = queryset.filter(fecha__gte=inicio, fecha__lt=fin)

        if metodo_pago:
            claves_validas = {c for c, _ in Factura.METODO_PAGO_CHOICES}
            if metodo_pago not in claves_validas:
                return queryset.none()
            queryset = queryset.filter(metodo_pago=metodo_pago)

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
        company = company_owner(self.request.user)

        # Reposición de stock + borrado, TODO atómico. select_for_update() bloquea
        # los productos para que una venta simultánea no pise la reposición. Si algo
        # falla, rollback completo (no queda factura borrada con stock sin reponer).
        with transaction.atomic():
            a_reponer = defaultdict(int)
            for producto_id, cantidad in (
                FacturaDetalle.objects
                .filter(factura=instance, tienda=company)
                .values_list('producto_id', 'cantidad')
            ):
                if producto_id is not None:
                    a_reponer[producto_id] += cantidad

            if a_reponer:
                productos = list(
                    ProductModel.objects
                    .select_for_update()
                    .filter(id__in=a_reponer.keys(), tienda=company)
                )
                for p in productos:
                    p.unidades_disponibles += a_reponer[p.id]
                    if p.unidades_disponibles > 0:
                        p.disponible = True
                ProductModel.objects.bulk_update(
                    productos, ['unidades_disponibles', 'disponible']
                )

            logger.info(
                "Factura %s eliminada por %s (tienda %s); stock repuesto en %d producto(s)",
                instance.id, getattr(self.request.user, 'email', self.request.user),
                company.id, len(a_reponer),
            )
            instance.delete()

    def delete(self, request, *args, **kwargs):
    
        instance = self.get_object()  # Obtiene la factura a eliminar
        self.perform_destroy(instance)  # Llama a perform_destroy
        return Response({"message": "Factura eliminada con éxito."},status=status.HTTP_204_NO_CONTENT)

