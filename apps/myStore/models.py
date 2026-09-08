from uuid import uuid4

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.core.validators import RegexValidator
from django.core.files.storage import default_storage

username_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9._]+$',
    message="Solo se permiten letras, números, puntos y guiones bajos. No se permiten espacios ni símbolos."
)

# Personalización del catálogo público. El backend solo guarda la clave; cada
# clave la traduce a una tipografía real la mini-app web (repo `catalog-web`),
# así se puede cambiar el typeface sin migración.
CATALOG_FONT_CHOICES = [
    ("", "Inter (por defecto)"),
    ("serif", "Serif elegante"),
    ("rounded", "Redondeada"),
    ("geometric", "Geométrica"),
    ("grotesk", "Grotesca moderna"),
]


def upload_to_catalog_banner(instance, filename):
    ext = filename.split(".")[-1].lower()
    slug = instance.name.replace(" ", "_").lower()
    return f"catalogo/banner/{slug}/{uuid4().hex}.{ext}"


class Company(models.Model):
    url_logo = models.ImageField(upload_to='profileCompany',null=True)
    nit = models.CharField(max_length=20, unique=True)  # NIT único
    company = models.CharField(max_length=255)
    name =models.CharField(
        max_length=255,
        unique=True,
        validators=[username_validator])
    phone = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    direction = models.CharField(max_length=255)
    municipality = models.CharField(max_length=100)
    # PROTECT: no se puede borrar un usuario que creó una empresa sin borrar
    # antes la empresa (evita arrastrar en cascada todo el historial).
    creator_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    # ---- Personalización del catálogo público (todo opcional) ----
    catalog_font = models.CharField(
        max_length=20, blank=True, default="", choices=CATALOG_FONT_CHOICES)
    catalog_tagline = models.CharField(max_length=120, blank=True, default="")
    catalog_announcement = models.CharField(max_length=140, blank=True, default="")
    catalog_banner = models.ImageField(
        upload_to=upload_to_catalog_banner, null=True, blank=True)

    def clean(self):
        clean_name = self.name.lower().strip()
        if Company.objects.filter(name__iexact=clean_name).exclude(pk=self.pk).exists():
            raise ValidationError("Este nombre ya está en uso.")
        self.name = clean_name

    
    def save(self, *args, **kwargs):
        # Si una imagen existente cambia, borra el archivo anterior del storage.
        if self.pk:
            try:
                old = Company.objects.get(pk=self.pk)
                for field in ("url_logo", "catalog_banner"):
                    old_file = getattr(old, field)
                    new_file = getattr(self, field)
                    if old_file and old_file != new_file:
                        if default_storage.exists(old_file.name):
                            default_storage.delete(old_file.name)
            except Company.DoesNotExist:
                pass

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.company

class Details_company(models.Model):
    nit = models.ForeignKey('myStore.Company', on_delete=models.CASCADE)  # Relación con Company
    dv = models.CharField(max_length=2)  # Dígito de verificación
    graphic_representation_name = models.CharField(max_length=255)
    registration_code = models.CharField(max_length=50, unique=True)
    economic_activity = models.CharField(max_length=10)  # Código de actividad económica

    def __str__(self):
        return f"Details of {self.nit}"

## Models Base global 


class BaseModel(models.Model):
    """Campos comunes de auditoría/multi-tenant.

    `tienda`, `creado_por` y `modificado_por` los asignan las vistas al llamar a
    `serializer.save(tienda=..., creado_por=...)` en `perform_create`. Antes había
    aquí un `save()` que dependía de un atributo `request_user` que nunca se
    asignaba (código muerto): eliminado.
    """
    tienda = models.ForeignKey('myStore.Company', on_delete=models.CASCADE, editable=False)
    # PROTECT: borrar un usuario NO debe arrastrar en cascada sus facturas /
    # productos / etc. Para borrar un usuario primero hay que resolver su historial.
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, editable=False, related_name="%(class)s_creados")
    modificado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="%(class)s_modificados")
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
