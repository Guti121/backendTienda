
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from apps.catalogo.api.serializers.serializers import CatalogoProductListSerializer, CatalogoProductRetrieveSerializer, CatalogoTipoProductListSerializer
from rest_framework.generics import ListAPIView,RetrieveAPIView
from apps.colletion.models import DescuentoProducto, ProductModel, TypeProductModel
from django.shortcuts import get_object_or_404
from apps.myStore.models import Company
from apps.catalogo.api.throttles import CatalogoAnonRateThrottle


class CatalogoPagination(PageNumberPagination):
    """Solo para el listado público del catálogo: 30 por página (el resto de la
    API sigue con el PAGE_SIZE global de 10). El cliente puede pedir otro tamaño
    con ?page_size=, hasta 60."""
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 60


# Vista para listar productos del catálogo de una tienda específica
# Permite buscar por nombre ('q'), filtrar por tipo de producto ('tipo') y
# ordenar por valor o fecha ('orden'/'fecha'). La tienda va en la URL.
class CatalogoListView(ListAPIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [CatalogoAnonRateThrottle]
    serializer_class = CatalogoProductListSerializer
    pagination_class = CatalogoPagination

    def get_queryset(self):
        name_param = self.kwargs.get('name')
        q_param = self.request.query_params.get('q')          # búsqueda por nombre
        tipo_param = self.request.query_params.get('tipo')
        orden_param = self.request.query_params.get('orden')  # 'asc' o 'desc'
        fecha_param = self.request.query_params.get('fecha')  # 'asc' o 'desc'

        if not name_param:
            raise ValidationError(detail="El parámetro 'name' es obligatorio.")

        tienda = get_object_or_404(Company, name__iexact=name_param)
        # Orden por defecto: sin un order_by explícito la paginación no es estable
        # (MySQL puede repetir o saltarse filas entre páginas y Django avisa con
        # UnorderedObjectListWarning). Los params 'fecha'/'orden' lo sobreescriben.
        queryset = (ProductModel.objects
                    .filter(disponible=True, publicar=True, tienda=tienda)
                    .select_related('tipo_producto')
                    .prefetch_related('imagenes', DescuentoProducto.prefetch_vigentes())
                    .order_by('-creado_en'))

        # Búsqueda por nombre (substring, case-insensitive por la collation de
        # MySQL). 'q' vacío o solo espacios se ignora (devuelve el listado
        # completo), no es un error.
        if q_param and q_param.strip():
            queryset = queryset.filter(nombre__icontains=q_param.strip())

        # Filtro por tipo de producto
        if tipo_param:
            try:
                tipo_param = int(tipo_param)
                queryset = queryset.filter(tipo_producto__id=tipo_param)
            except ValueError:
                raise ValidationError(detail="El parámetro 'tipo' debe ser numérico.")

        # Ordenamiento (sobreescribe el orden por defecto). Siempre con 'id' de
        # desempate para que la paginación sea determinista.
        if fecha_param in ['asc', 'desc']:
            queryset = queryset.order_by(
                'creado_en' if fecha_param == 'asc' else '-creado_en', 'id')
        elif orden_param in ['asc', 'desc']:
            queryset = queryset.order_by(
                'valor' if orden_param == 'asc' else '-valor', 'id')

        return queryset


class CatalogoProductRetrieveView(RetrieveAPIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [CatalogoAnonRateThrottle]
    serializer_class = CatalogoProductRetrieveSerializer

    def get_object(self):
        name_param = self.kwargs.get('name')
        product_id = self.kwargs.get('id')

        if not name_param or not product_id:
            raise ValidationError(detail="Los parámetros 'name' e 'id' son obligatorios.")

        tienda = get_object_or_404(Company, name__iexact=name_param)
        product = get_object_or_404(
            ProductModel.objects.select_related('tipo_producto')
                .prefetch_related('imagenes', DescuentoProducto.prefetch_vigentes()),
            id=product_id, tienda=tienda, disponible=True, publicar=True,
        )
        
        if not product:
            raise ValidationError(detail="Producto no encontrado o no disponible.")

        return product

# Vista para listar tipos de productos de una tienda específica
# Requiere el nombre de la tienda como parámetro en la URL
class CatalogoTipoProductListView(ListAPIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [CatalogoAnonRateThrottle]
    serializer_class = CatalogoTipoProductListSerializer
    # Lista corta (las categorías de una tienda): se devuelve completa, sin
    # paginar, para que el menú de categorías del catálogo no se corte.
    pagination_class = None

    def get_queryset(self):
        name_param = self.kwargs.get('name')

        if not name_param:
            raise ValidationError(detail="El parámetro 'name' es obligatorio.")

        tienda = get_object_or_404(Company, name__iexact=name_param)
        queryset = TypeProductModel.objects.filter(tienda=tienda)
        if not queryset.exists():
            raise ValidationError(detail="No se encontraron tipos de productos para esta tienda.")
        return queryset
