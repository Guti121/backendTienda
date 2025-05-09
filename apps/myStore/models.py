from django.conf import settings
from django.db import models

class Company(models.Model):
    url_logo = models.URLField(max_length=500)
    nit = models.CharField(max_length=20, unique=True)  # NIT único
    company = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    direction = models.CharField(max_length=255)
    municipality = models.CharField(max_length=100)
    creator_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

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
