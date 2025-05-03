from django.contrib import admin

from apps.base.models import CustomUser, UserProfile

class BaseModelsAdmin(admin.ModelAdmin):

    """Clase base para administrar modelos, excluyendo auto_now/auto_now_add y fijando readonly_fields."""

    only_read = ('id','tienda', 'creado_por', 'modificado_por', 'creado_en', 'modificado_en')

    def get_fields(self, request, obj=None):
        """Obtiene todos los campos del modelo, excluyendo auto_now y auto_now_add."""
        return [
            field.name for field in self.model._meta.fields
            if not (getattr(field, 'auto_now_add', False))
        ]

    def get_readonly_fields(self, request, obj=None):
        """Hace que los campos en only_read y los que tienen auto_now/auto_now_add sean de solo lectura."""
        auto_fields = [
            field.name for field in self.model._meta.fields
            if  getattr(field, 'auto_now_add', False)
        ]
        return list(self.only_read) + auto_fields  # Combina los campos manuales con los auto_now


# Register your models here.
admin.site.register(UserProfile)
admin.site.register(CustomUser)