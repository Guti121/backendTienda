from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.generics import DestroyAPIView,ListAPIView
from Tienda_Virtual.globalFunctions import company_owner
from apps.myStore.api.permissions import IsCompanyMember
from apps.myStore.models import Company
from apps.base.api.user.viewsPermissions import IsAdminOrCreator,isCreator
from apps.colletion.models import ProductModel,TypeProductModel
from apps.colletion.api.serializers.serializer import TypeProductModelSerializer,TypeProductModelDestroySerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.db.models.functions import Lower
from rest_framework.exceptions import PermissionDenied

class TypeProductListView(ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsAdminOrCreator]
    serializer_class=TypeProductModelSerializer
    
    def get_queryset(self):
        company = company_owner(self.request.user)
        queryset = TypeProductModel.objects.filter(tienda=company).order_by(Lower('tipo_producto'))
       
        
        query = self.request.GET.get('q', None)
        if query:
            queryset = queryset.filter(tipo_producto__icontains=query).order_by(Lower('tipo_producto'))
            
        return queryset

class TypeProductFilterAdminAPIView(generics.ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated,IsAdminOrCreator]
    serializer_class =TypeProductModelSerializer

    def get_queryset(self):
        company = company_owner(self.request.user)
        queryset = TypeProductModel.objects.filter(tienda=company).order_by(Lower('tipo_producto'))
       
        
        query = self.request.GET.get('q', None)
        if query:
            queryset = queryset.filter(tipo_producto__icontains=query).order_by(Lower('tipo_producto'))
            
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

class TypeProductCreateView(generics.CreateAPIView):
    serializer_class = TypeProductModelSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]
    queryset = TypeProductModel.objects.all()

    def create(self, request, *args, **kwargs):
        tipo_producto = request.data.get('tipo_producto')
        if not tipo_producto:
            return Response({"error": "El valor no puede estar vacío."}, status=status.HTTP_400_BAD_REQUEST)

        self.company = company_owner(self.request.user)  # Guardar en self para reutilizar

        if TypeProductModel.objects.filter(tipo_producto=tipo_producto, tienda=self.company).exists():
            return Response(
                {"error": f"El tipo de producto '{tipo_producto}' ya existe."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user, tienda=self.company)


class TypeProductDestroyAPIView(DestroyAPIView):
    serializer_class1=TypeProductModelDestroySerializer
    authentication_classes = [JWTAuthentication]  # Agrega JWTAuthentication
    permission_classes = [IsAuthenticated,IsAdminOrCreator]  # Agrega IsAuthenticated
   
    

    def delete(self, request, pk=None):
    
        # Verificamos que el token del user_clie que va a hacer la reserva coincida con el ususario autenticado en ese momento
        company = company_owner(self.request.user)
        
        Type_product = TypeProductModelDestroySerializer.Meta.model.objects.filter(id=pk,tienda=company).first()
        if Type_product:
            Type_product.delete()
            return Response({'message': 'Formularios eliminados correctamente'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Este objeto no se encuentra en la base de datos'}, status=status.HTTP_400_BAD_REQUEST)
