from django.urls import path

from apps.inventario.api.inventrio_views import InventarioMesView, InventarioProductos, InventarioView, ResumenVentasMensualView


urlpatterns =[
    path('',InventarioView.as_view(), name='List Inventario'),
    path('mensual/',InventarioMesView.as_view(), name='List Inventario'),
    path('resumen/', ResumenVentasMensualView.as_view(), name='Resumen Ventas Mens'),
    path('productos/',InventarioProductos.as_view(), name='inventario de productos')


]