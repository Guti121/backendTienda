from django.conf import settings
from django.db import models

# Create your models here.
#Realizamos la creacion de la tabla usuario 
from django.contrib.auth import get_user_model

from django.contrib.auth.models import AbstractUser

#Custom User
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)  # El correo debe ser único
    first_name = models.CharField(max_length=150, blank=False, null=False)  # No puede ser nulo ni vacío
    last_name = models.CharField(max_length=150, blank=False, null=False)   # No puede ser nulo ni vacío

    USERNAME_FIELD = 'email'  # Se usará el email para autenticarse en lugar del username
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']  # Ahora también se requieren estos campos

    def save(self, *args, **kwargs):
            # Convierte la primera letra en mayúscula y el resto en minúsculas
            self.first_name = self.first_name.capitalize()  
            self.last_name = self.last_name.capitalize()
            super().save(*args, **kwargs)  # Llamar al método save original
    def __str__(self):
        return self.email

#Tables user Roles 
class TipoUsuario(models.TextChoices):
    ADMIN = "admin", "Administrador"
    CREATOR = "creator", "Creador"
    WORKER = "worker", "Trabajador"
    CLIENTE= "cliente",'Cliente'

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    company = models.ForeignKey("myStore.Company", on_delete=models.SET_NULL, null=True, blank=True)  # Relación con la empresa
    tipo_usuario = models.CharField(
        max_length=20,
        choices=TipoUsuario.choices,
        default=TipoUsuario.CLIENTE
    )

    def __str__(self):
        return f"{self.user.username} - {self.tipo_usuario} - {self.company}"

User = get_user_model()

