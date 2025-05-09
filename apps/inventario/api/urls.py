from django.urls import path

from apps.inventario.api.inventrio_views import InventarioView, InventarioViewFilter


urlpatterns =[
    path('',InventarioView.as_view(), name='List Inventario'),
    path('filter/',InventarioViewFilter.as_view(), name='List Inventario'),

]