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
    creator_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def clean(self):
        clean_name = self.name.lower().strip()
        if Company.objects.filter(name__iexact=clean_name).exclude(pk=self.pk).exists():
            raise ValidationError("Este nombre ya está en uso.")
        self.name = clean_name

    
    def save(self, *args, **kwargs):
        # Verifica si ya existía una imagen y si está cambiando
        if self.pk:
            try:
                old = Company.objects.get(pk=self.pk)
                if old.url_logo and old.url_logo != self.url_logo:
                    if default_storage.exists(old.url_logo.name):
                        default_storage.delete(old.url_logo.name)
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
    tienda = models.ForeignKey('myStore.Company', on_delete=models.CASCADE, editable=False)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, editable=False, related_name="%(class)s_creados")
    modificado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="%(class)s_modificados")
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        
    def save(self, *args, **kwargs):
        if not self.tienda and hasattr(self, "request_user"):
            self.tienda = self.request_user.profile.tienda
        if not self.creado_por and hasattr(self, "request_user"):
            self.creado_por = self.request_user
        if hasattr(self, "request_user"):
            self.modificado_por = self.request_user
        super().save(*args, **kwargs)
