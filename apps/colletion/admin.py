from django.contrib import admin

# Register your models here.

from apps.base.admin import BaseModelsAdmin
from apps.colletion.models import  Bar_codeModel, CategoryModel, Config_ProductModel, DescuentoProducto, ProductImage, ProductModel,TypeProductModel
admin.site.register(ProductModel,BaseModelsAdmin)
admin.site.register(TypeProductModel,BaseModelsAdmin)
admin.site.register(CategoryModel,BaseModelsAdmin)
admin.site.register(Bar_codeModel,BaseModelsAdmin)
admin.site.register(Config_ProductModel,BaseModelsAdmin)
admin.site.register(ProductImage,BaseModelsAdmin)
admin.site.register(DescuentoProducto,BaseModelsAdmin)