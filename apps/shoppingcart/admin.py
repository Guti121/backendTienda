from django.contrib import admin

# Register your models here.

from apps.base.admin import BaseModelsAdmin
from apps.shoppingcart.models import Factura,FacturaDetalle





admin.site.register(FacturaDetalle,BaseModelsAdmin)
admin.site.register(Factura, BaseModelsAdmin)
