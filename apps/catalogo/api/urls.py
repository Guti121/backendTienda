
from django.urls import path 
from apps.catalogo.api.views.views import CatalogoListView, CatalogoProductRetrieveView, CatalogoTipoProductListView
from apps.catalogo.api.views.viewsCompany import CompanyDetailView


urlpatterns=[
    path('list/<str:name>', CatalogoListView().as_view(), name='catalogo-product-list'),
    path('product/<str:name>/<int:id>', CatalogoProductRetrieveView().as_view(), name='catalogo-product-detail'),
    path('tipo-producto/<str:name>', CatalogoTipoProductListView().as_view(), name='catalogo-tipo-product-list'),

    #Comapany
    path('company/<str:name>', CompanyDetailView().as_view(), name='catalogo-company-detail'),
]