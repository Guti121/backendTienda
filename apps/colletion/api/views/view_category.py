from rest_framework import generics
from Tienda_Virtual.globalFunctions import company_owner
from apps.base.api.user.viewsPermissions import IsAdminOrCreator
from apps.colletion.models import CategoryModel
from apps.colletion.api.serializers.serializer import CategoryModelSerializer, CategoryModelDestroySerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework.permissions import IsAuthenticated
from django.db.models.functions import Lower


class CategoryListView(generics.ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]
    serializer_class = CategoryModelSerializer

    def get_queryset(self):
        company = company_owner(self.request.user)
        queryset = CategoryModel.objects.filter(tienda=company).order_by(Lower('nombre'))

        query = self.request.GET.get('q', None)
        if query:
            queryset = queryset.filter(nombre__icontains=query).order_by(Lower('nombre'))

        return queryset


class CategoryFilterAdminAPIView(generics.ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]
    serializer_class = CategoryModelSerializer

    def get_queryset(self):
        company = company_owner(self.request.user)
        queryset = CategoryModel.objects.filter(tienda=company).order_by(Lower('nombre'))

        query = self.request.GET.get('q', None)
        if query:
            queryset = queryset.filter(nombre__icontains=query).order_by(Lower('nombre'))

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        if not queryset:
            return Response({'error': 'No se encontraron categorías con esas características!'}, status=status.HTTP_404_NOT_FOUND)

        return Response(self.get_serializer(queryset, many=True).data)


class CategoryCreateView(generics.CreateAPIView):
    serializer_class = CategoryModelSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]
    queryset = CategoryModel.objects.all()

    def create(self, request, *args, **kwargs):
        nombre = request.data.get('nombre')
        if not nombre:
            return Response({"error": "El valor no puede estar vacío."}, status=status.HTTP_400_BAD_REQUEST)

        self.company = company_owner(self.request.user)

        if CategoryModel.objects.filter(nombre=nombre, tienda=self.company).exists():
            return Response(
                {"error": f"La categoría '{nombre}' ya existe."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user, tienda=self.company)


class CategoryUpdateAPIView(generics.UpdateAPIView):
    serializer_class = CategoryModelSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]

    def get_queryset(self):
        company = company_owner(self.request.user)
        return CategoryModel.objects.filter(tienda=company)

    def perform_update(self, serializer):
        serializer.save(modificado_por=self.request.user)


class CategoryDestroyAPIView(generics.DestroyAPIView):
    serializer_class1 = CategoryModelDestroySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]

    def delete(self, request, pk=None):
        company = company_owner(self.request.user)

        category = CategoryModelDestroySerializer.Meta.model.objects.filter(id=pk, tienda=company).first()
        if category:
            category.delete()
            return Response({'message': 'Categoría eliminada correctamente'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Este objeto no se encuentra en la base de datos'}, status=status.HTTP_400_BAD_REQUEST)
