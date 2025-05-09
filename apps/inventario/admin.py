from django.contrib import admin

from apps.inventario.models import ReporteVentasDiario, ReporteVentasMensual

# Register your models here.
admin.site.register(ReporteVentasDiario)
admin.site.register(ReporteVentasMensual)