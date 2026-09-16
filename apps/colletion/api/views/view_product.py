import random
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from rest_framework import generics
from rest_framework.generics import DestroyAPIView,ListAPIView
from Tienda_Virtual.globalFunctions import company_owner, profile_user
from apps.base.api.user.viewsPermissions import IsAdminOrCreator, IsWorkerOrCreator, isCreator, isWorker
from apps.colletion.models import DescuentoProducto, ProductImage, ProductModel
from apps.colletion.api.serializers.serializer import ProductModelListFilterSerializer, ProductModelRetrieveProductCreatorSerializer, ProductModelRetrieveProductSerializer,ProductModelSerializer,ProductModelDestroySerializer, ProductModelUpdateProductSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from django.db.models.functions import Lower
from rest_framework_simplejwt.authentication import JWTAuthentication


def _productos_de(company):
    """Queryset base de productos de una tienda, con las relaciones que usan los
    serializers ya cargadas (evita N+1 por 'tipo_producto' e 'imagenes')."""
    return (ProductModel.objects
            .filter(tienda=company)
            .select_related('tipo_producto')
            .prefetch_related('imagenes', DescuentoProducto.prefetch_vigentes())
            .order_by('id'))  # orden estable por defecto (paginación determinista)


def _busqueda_producto_q(query, incluir_detalles=False):
    """Condición de búsqueda de producto. 'valor' (Decimal) se compara exacto
    solo si `query` parsea como número, en lugar de un LIKE que castea toda la
    columna en cada fila."""
    cond = Q(nombre__icontains=query) | Q(numero_producto__icontains=query)
    if incluir_detalles:
        cond |= Q(detalles__icontains=query)
    try:
        cond |= Q(valor=Decimal(query))
    except (InvalidOperation, TypeError):
        pass
    return cond


##Podemos listar los productos en general sin ningun filtro
class ListProductAPIView(ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsAdminOrCreator]
    serializer_class = ProductModelListFilterSerializer

    def get_queryset(self):
        return _productos_de(company_owner(self.request.user))

##Podemos listar un producto en especifico  
class ProductRetrieveAPIView(generics.RetrieveAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsWorkerOrCreator]

    def get_serializer_class(self):
        if profile_user(self.request.user) == "creator":
            return ProductModelRetrieveProductCreatorSerializer
        else:
            return ProductModelRetrieveProductSerializer

    def get_queryset(self):
        return _productos_de(company_owner(self.request.user))

    def retrieve(self, request, *args, **kwargs):
        pk = kwargs.get("pk")
        try:
            instance = self.get_queryset().get(pk=pk)
        except ProductModel.DoesNotExist:
            return Response({"error": "El producto solicitado no existe."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

        
##Podemos FILTRAR por productos
class ProductFilterAdminAPIView(generics.ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsAdminOrCreator]
    serializer_class = ProductModelListFilterSerializer

    def get_queryset(self):
        company = company_owner(self.request.user)
        queryset = _productos_de(company).order_by(Lower('nombre'))

        query = self.request.GET.get('q', None)
        if query:
            queryset = queryset.filter(_busqueda_producto_q(query))

        ##filtrar por orden
        filter = self.request.GET.get('order', None)
        if filter == "0":  # Orden ascendente
            queryset = queryset.filter(unidades_disponibles=0)
        elif filter == "1":  # Orden ascendente de unidades
            queryset = queryset.filter(unidades_disponibles__gt=0).order_by('-unidades_disponibles')
        elif filter == "2":  # Orden ascendente de unidades
            queryset = queryset.filter(unidades_disponibles__gt=0).order_by('unidades_disponibles')
        elif filter == "3":  # Orden descendente por fecha de creación
            queryset = queryset.order_by('-creado_en')
        elif filter == "4":  # Orden ascendente por fecha de creación
            queryset = queryset.order_by('creado_en')
        elif filter == "5":  # Orden ascendente de unidades
            queryset = queryset.order_by(Lower('nombre'))

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        if not queryset:
            return Response({'error': 'No se encontraron productos con esas características!'}, status=status.HTTP_404_NOT_FOUND)

        return Response(self.get_serializer(queryset, many=True).data)

#clase para filtrar los objetos que contengan algun caracter que se pase desde el frontend     
class ProductListFilterAPIView( generics.ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsWorkerOrCreator]
    serializer_class = ProductModelListFilterSerializer

    def get_queryset(self):
        company = company_owner(self.request.user)
        queryset = _productos_de(company).filter(unidades_disponibles__gt=0, disponible=True)
        query = self.request.GET.get('q', None)
        if query:
            queryset = queryset.filter(_busqueda_producto_q(query, incluir_detalles=True))
        return queryset[:10]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset:
            return Response({'error': 'No se encontraron productos con esas características!'}, status=status.HTTP_404_NOT_FOUND)

        # Aquí se debe devolver una instancia de Response con los datos serializados
        return Response(self.get_serializer(queryset, many=True).data)
    
    
class ProductCreateView( generics.CreateAPIView):
    serializer_class = ProductModelSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,isCreator]
    
    # La validación del alta vive en ProductModelSerializer.validate(); aquí solo
    # se asignan tienda y creador. CreateAPIView.create() hace el resto
    # (is_valid -> 400 con errores por campo, perform_create, 201).
    def perform_create(self, serializer):
        serializer.save(
            creado_por=self.request.user,
            tienda=company_owner(self.request.user),
        )



class ProductDestroyAPIView(DestroyAPIView):
    serializer_class = ProductModelDestroySerializer  # Corregido el nombre
    authentication_classes = [JWTAuthentication]  
    permission_classes = [IsAuthenticated,IsAdminOrCreator]  

    def delete(self, request, pk=None):
        # Verificar autenticación
        if not request.user or not request.user.is_authenticated:
            return Response({'error': 'Usuario no autorizado.'}, status=status.HTTP_403_FORBIDDEN)

      
        # Obtener el producto
         
        company = company_owner(self.request.user)
        product = ProductModel.objects.filter(id=pk, tienda = company).first()
        if not product:
            return Response({'error': 'No existe un formulario con estos datos!'}, status=status.HTTP_400_BAD_REQUEST)

        # No se borra un producto con ventas registradas: al hacerlo el
        # FacturaDetalle queda con producto=NULL y el stock ya no se puede
        # reponer si luego se anula la factura. Mejor "despublicarlo".
        from apps.shoppingcart.models import FacturaDetalle
        if FacturaDetalle.objects.filter(producto=product).exists():
            return Response(
                {'error': 'Este producto tiene ventas registradas y no se puede eliminar. '
                          'Puedes ocultarlo del catálogo con "publicar" y dejar el stock en 0.'},
                status=status.HTTP_409_CONFLICT,
            )

        # ✅ Eliminar imágenes asociadas
        for img in product.imagenes.all():
            img.imagen.delete(save=False)  # Elimina archivo del storage (S3)
            img.delete()                   # Elimina registro del modelo

        # Eliminar el producto
        product.delete()
        return Response({'message': 'Producto eliminado correctamente'}, status=status.HTTP_200_OK)


class ProductUpdateApiView(generics.UpdateAPIView):
    serializer_class = ProductModelUpdateProductSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsAdminOrCreator]


    def get_queryset(self):
        company= company_owner(self.request.user)
        queryset = ProductModel.objects.filter(tienda=company)  # ✅ Corrección de queryset

        return queryset
    
    def patch(self, request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response({'error': 'Usuario no autorizado.'}, status=status.HTTP_403_FORBIDDEN)

        pk = kwargs.get('pk')
        product = self.get_queryset().filter(id=pk).first()

        if not product:
            return Response({'error': 'Producto no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            unidades_disponibles = request.data.get('unidades_disponibles')
            if unidades_disponibles is not None:
                unidades_disponibles = int(unidades_disponibles)
                product.disponible = unidades_disponibles > 0

            try:
                serializer.save(modificado_por=self.request.user)

                # ✅ MANEJAR ARCHIVOS
                imagenes_files = request.FILES.getlist("imagenes")

                                
                # Si el usuario explícitamente manda imágenes vacías
                if "imagenes" in request.FILES and not imagenes_files:
                    for img in product.imagenes.all():
                        img.imagen.delete(save=False)  # Borra el archivo de S3/local
                        img.delete()  # Borra el objeto del modelo
                if imagenes_files and len(imagenes_files) > 5:
                    return Response({'error': 'No puedes subir más de 5 imágenes por producto.'}, status=status.HTTP_400_BAD_REQUEST)   
                # Eliminar imágenes existentes si se envían nuevas
                if imagenes_files:
                    for img in product.imagenes.all():
                        img.imagen.delete(save=False)  # Borra el archivo de S3/local
                        img.delete()  # Borra el objeto del modelo
                    for image in imagenes_files:
                        company = company_owner(request.user)
                    
                        ProductImage.objects.create(producto=product, 
                                                    imagen=image,
                                                    tienda=company,
                                                    creado_por=request.user,  # Asigna el usuario que crea el producto
                                                    creado_en=timezone.now(),)

                return Response(serializer.data, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': f'Error al guardar el producto: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
