from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from Tienda_Virtual.globalFunctions import company_owner
from apps.base.api.user.viewsPermissions import IsAdminOrCreator
from apps.colletion.api.serializers.serializer_descuento import (
    DescuentoProductoListSerializer,
    DescuentoProductoSerializer,
)
from apps.colletion.models import DescuentoProducto


class DescuentoProductoCreateView(generics.CreateAPIView):
    serializer_class = DescuentoProductoSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]

    def perform_create(self, serializer):
        serializer.save(
            creado_por=self.request.user,
            tienda=company_owner(self.request.user),
        )


class DescuentoProductoListView(generics.ListAPIView):
    serializer_class = DescuentoProductoListSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]

    def get_queryset(self):
        company = company_owner(self.request.user)
        queryset = DescuentoProducto.objects.filter(producto__tienda=company).order_by('-creado_en')
        producto_id = self.request.query_params.get('producto')
        if producto_id:
            queryset = queryset.filter(producto_id=producto_id)
        return queryset


class DescuentoProductoUpdateView(generics.UpdateAPIView):
    serializer_class = DescuentoProductoSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]

    def get_queryset(self):
        company = company_owner(self.request.user)
        return DescuentoProducto.objects.filter(producto__tienda=company)

    def perform_update(self, serializer):
        serializer.save(modificado_por=self.request.user)


class DescuentoProductoDestroyView(generics.DestroyAPIView):
    serializer_class = DescuentoProductoSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]

    def get_queryset(self):
        company = company_owner(self.request.user)
        return DescuentoProducto.objects.filter(producto__tienda=company)
