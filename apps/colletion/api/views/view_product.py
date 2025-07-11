from calendar import c
import random
from django.utils import timezone
from rest_framework import generics
from rest_framework.generics import DestroyAPIView,ListAPIView
from Tienda_Virtual.globalFunctions import company_owner, profile_user
from apps.base.api.user.viewsPermissions import IsAdminOrCreator, IsWorkerOrCreator, isCreator, isWorker
from apps.colletion.models import ProductImage, ProductModel
from apps.base.api.token.authentication_mixins import Authentication
from apps.colletion.api.serializers.serializer import ProductModelListFilterSerializer, ProductModelRetrieveProductCreatorSerializer, ProductModelRetrieveProductSerializer,ProductModelSerializer,ProductModelDestroySerializer, ProductModelUpdateProductSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from django.db.models.functions import Lower
from rest_framework_simplejwt.authentication import JWTAuthentication


##Podemos listar los productos en general sin ningun filtro    
class ListProductAPIView(ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsAdminOrCreator]
    serializer_class = ProductModelListFilterSerializer

    def get_queryset(self):
        company = company_owner(self.request.user)
        return ProductModel.objects.filter(tienda=company)

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
        company = company_owner(self.request.user)
        return ProductModel.objects.filter(tienda=company)
    
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
        queryset = ProductModel.objects.filter(tienda=company).order_by(Lower('nombre'))
       
        
        query = self.request.GET.get('q', None)
        if query:
            queryset = queryset.filter(
                Q(nombre__icontains=query) | 
                Q(valor__icontains=query) |
                Q(numero_producto__icontains=query)
            )
            
        ##filtrar por orden 
        filter = self.request.GET.get('order', None)
        print(type(filter))
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
        queryset = ProductModel.objects.filter(tienda = company ,unidades_disponibles__gt=0,disponible=True)
        query = self.request.GET.get('q', None)
        if query:
            queryset = queryset.filter(
                Q(nombre__icontains=query) | 
                Q(detalles__icontains=query) |
                Q(valor__icontains=query)|
                Q(numero_producto__icontains=query)
            )
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
    
    def create(self, request, *args, **kwargs):
        # Crear una copia mutable de los datos
        data = request.data.copy()

        # Validar campos requeridos directamente desde el serializador
        valor = data.get('valor')
        unidades_disponibles = data.get('unidades_disponibles')
        valor_mayor =data.get('valor_mayor')
        tipo_producto=data.get('tipo_producto')
        nombre_producto=data.get('nombre')

        # Buscamos la tienda a la que pertenece el usuario 
        company= company_owner(self.request.user)

        if ProductModel.objects.filter(tienda = company ,nombre=nombre_producto).exists():
            return Response(
                {"error": "Este producto ya existe en la base de datos."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not valor or not unidades_disponibles or not tipo_producto:
            return Response(
                {"error": "Verifique los campos, parece que alguno está vacío."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar unidades disponibles
        try:
            if int(unidades_disponibles) <= 0:
                return Response(
                    {"error": "Las unidades disponibles no pueden ser menores o iguales a 0."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            return Response(
                {"error": "El campo 'unidades disponibles' debe ser un número válido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar valor como número decimal positivo
        try:
            valor_decimal = float(valor)
            if valor_decimal <= 0.00:
                return Response(
                    {"error": "El 'valor' debe ser mayor a 0."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            return Response(
                {"error": "El 'valor' debe ser un número válido."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            valor_decimal = float(valor)
            if valor_decimal < float(valor_mayor):
                return Response(
                    {"error": "El valor de venta debe ser superior al valor al por mayor."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            return Response(
                {"error": "El 'valor por mayor' debe ser un número válido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Agregar el campo 'disponible' según las unidades
        data['disponible'] = True if int(unidades_disponibles) > 0 else False

        # Validar y guardar los datos con el serializador
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def perform_create(self, serializer):
        """Asigna automáticamente la empresa del usuario al producto antes de guardarlo."""
        company = company_owner(self.request.user)  # Obtener la empresa del usuario
        serializer.save(creado_por=self.request.user, tienda=company)



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
                if imagenes_files:
                    product.imagenes.all().delete()
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
