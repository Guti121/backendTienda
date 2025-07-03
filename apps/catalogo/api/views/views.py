
from rest_framework.exceptions import ValidationError
from apps.catalogo.api.serializers.serializers import CatalogoProductListSerializer, CatalogoProductRetrieveSerializer, CatalogoTipoProductListSerializer
from rest_framework.generics import ListAPIView,RetrieveAPIView
from apps.colletion.models import ProductModel, TypeProductModel
from django.shortcuts import get_object_or_404
from apps.myStore.models import Company

# Vista para listar productos del catálogo de una tienda específica
# Permite filtrar por tipo de producto, ordenar por valor o fecha, y requiere el
class CatalogoListView(ListAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = CatalogoProductListSerializer

    def get_queryset(self):
        name_param = self.kwargs.get('name')
        tipo_param = self.request.query_params.get('tipo')
        orden_param = self.request.query_params.get('orden')  # 'asc' o 'desc'
        fecha_param = self.request.query_params.get('fecha')  # 'asc' o 'desc'

        if not name_param:
            raise ValidationError(detail="El parámetro 'name' es obligatorio.")

        tienda = get_object_or_404(Company, name__iexact=name_param)
        queryset = ProductModel.objects.filter(disponible=True, publicar=True, tienda=tienda)

        # Filtro por tipo de producto
        if tipo_param:
            try:
                tipo_param = int(tipo_param)
                queryset = queryset.filter(tipo_producto__id=tipo_param)
            except ValueError:
                raise ValidationError(detail="El parámetro 'tipo' debe ser numérico.")

        # Ordenamiento
        if fecha_param in ['asc', 'desc']:
            queryset = queryset.order_by('creado_en' if fecha_param == 'asc' else '-creado_en')
        elif orden_param in ['asc', 'desc']:
            queryset = queryset.order_by('valor' if orden_param == 'asc' else '-valor')

        return queryset


class CatalogoProductRetrieveView(RetrieveAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = CatalogoProductRetrieveSerializer

    def get_object(self):
        name_param = self.kwargs.get('name')
        product_id = self.kwargs.get('id')

        if not name_param or not product_id:
            raise ValidationError(detail="Los parámetros 'name' e 'id' son obligatorios.")

        tienda = get_object_or_404(Company, name__iexact=name_param)
        product = get_object_or_404(ProductModel, id=product_id, tienda=tienda, disponible=True, publicar=True)
        
        if not product:
            raise ValidationError(detail="Producto no encontrado o no disponible.")

        return product

# Vista para listar tipos de productos de una tienda específica
# Requiere el nombre de la tienda como parámetro en la URL
class CatalogoTipoProductListView(ListAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = CatalogoTipoProductListSerializer

    def get_queryset(self):
        name_param = self.kwargs.get('name')

        if not name_param:
            raise ValidationError(detail="El parámetro 'name' es obligatorio.")

        tienda = get_object_or_404(Company, name__iexact=name_param)
        queryset = TypeProductModel.objects.filter(tienda=tienda)
        if not queryset.exists():
            raise ValidationError(detail="No se encontraron tipos de productos para esta tienda.")
        return queryset
