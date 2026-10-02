# urls.py
from django.urls import path
from .views import FacturasCreateView,FacturasListView,FacturasDetailView,FacturaDestroyView
from .views_caja import (
    CajaAbrirView, CajaActualView, CajaResumenView, CajaCerrarView,
    MovimientoCajaCreateView, CajaHistorialListView,
)
from .codebar import LecturaCodigoBarrasAPIView,LecturaCodigoBarrasTextAPIView, RetrieveBarCode

urlpatterns = [
    path('', FacturasListView.as_view(), name='factura-list'),
    path('<int:pk>/', FacturasDetailView.as_view(), name='factura-detail'),
    path('create/', FacturasCreateView.as_view(), name='factura-create'),
    path('destroy/<int:pk>/',FacturaDestroyView.as_view(),name='destroy Factura'),


    #codigo de barras
    path('codigo_de_barras/',LecturaCodigoBarrasAPIView.as_view(),name='lector codigo de barras'),
    path('codigo_de_barras_text/',LecturaCodigoBarrasTextAPIView.as_view(),name='lector codigo de barras por texto'),
    path('api/barcode/<int:pk>/', RetrieveBarCode.as_view(), name='barcode-detail'),

    #caja
    path('caja/abrir/', CajaAbrirView.as_view(), name='caja-abrir'),
    path('caja/actual/', CajaActualView.as_view(), name='caja-actual'),
    path('caja/resumen/', CajaResumenView.as_view(), name='caja-resumen'),
    path('caja/cerrar/', CajaCerrarView.as_view(), name='caja-cerrar'),
    path('caja/movimiento/', MovimientoCajaCreateView.as_view(), name='caja-movimiento'),
    path('caja/historial/', CajaHistorialListView.as_view(), name='caja-historial'),

]
