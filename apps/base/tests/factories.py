"""Helpers compartidos por la suite de tests (no es un módulo de tests)."""
import base64
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.base.models import CustomUser, TipoUsuario, UserProfile
from apps.colletion.models import DescuentoProducto, ProductModel, TypeProductModel
from apps.myStore.models import Company

# PNG 1x1 válido (los serializers DRF validan que sea una imagen real).
_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def png_file(name="img.png"):
    return SimpleUploadedFile(name, _PNG_1x1, content_type="image/png")


def make_user(username, tipo=TipoUsuario.CLIENTE, company=None):
    user = CustomUser.objects.create_user(
        username=username, email=f"{username}@test.com", password="pass12345",
        first_name=username.title(), last_name="Test",
    )
    UserProfile.objects.create(user=user, company=company, tipo_usuario=tipo)
    return user


def make_company(nombre="tiendatest", email="empresa@test.com", nit="900123"):
    creador = CustomUser.objects.create_user(
        username=f"creador_{nombre}", email=f"creador_{nombre}@test.com",
        password="pass12345", first_name="Cre", last_name="Ador",
    )
    company = Company.objects.create(
        nit=nit, company="Tienda Test", name=nombre, phone="123",
        email=email, direction="Calle 1", municipality="Bogota",
        creator_user=creador, url_logo=png_file("logo.png"),
    )
    UserProfile.objects.create(user=creador, company=company, tipo_usuario=TipoUsuario.CREATOR)
    return company, creador


def make_tipo(company, creador, nombre="General"):
    return TypeProductModel.objects.create(
        tipo_producto=nombre, tienda=company, creado_por=creador,
    )


def make_product(company, creador, nombre="Producto A", stock=10, valor="1000",
                 valor_mayor="500", tipo=None):
    tipo = tipo or make_tipo(company, creador)
    return ProductModel.objects.create(
        nombre=nombre, tipo_producto=tipo, detalles="x",
        valor_mayor=Decimal(valor_mayor), valor=Decimal(valor),
        unidades_disponibles=stock, tienda=company, creado_por=creador,
    )


def make_descuento(producto, creador, porcentaje="10", dias=7, activo=True, inicio=None):
    inicio = inicio or timezone.now()
    return DescuentoProducto.objects.create(
        producto=producto, porcentaje=Decimal(porcentaje),
        fecha_inicio=inicio, fecha_fin=inicio + timedelta(days=dias),
        activo=activo, tienda=producto.tienda, creado_por=creador,
    )
