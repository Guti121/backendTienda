# urls.py
from django.urls import path
from .views import FacturasCreateView,FacturasListView,FacturasDetailView,FacturaDestroyView
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
    
]
