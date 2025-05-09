from django.urls import path
from apps.colletion.api.views.view_config_price import ConfigProductoRetrieveAPIView, CreacionParametrosAPIView, EliminacionParametrosAPIView, PrecioSugeridoAPIView
from apps.colletion.api.views.view_product import ProductCreateView,ProductDestroyAPIView,ListProductAPIView, ProductFilterAdminAPIView,ProductListFilterAPIView,ProductRetrieveAPIView, ProductUpdateApiView
from apps.colletion.api.views.view_typeproduct import TypeProductCreateView,TypeProductDestroyAPIView, TypeProductFilterAdminAPIView, TypeProductListView

urlpatterns=[
    
    path('list/', ListProductAPIView.as_view(), name='list colletions'),
    path('listfilter/',ProductListFilterAPIView.as_view(), name='List Filter product'),
    path('product/', ProductFilterAdminAPIView.as_view(), name='list product colletions'),
    path('productDetail/<int:pk>/', ProductRetrieveAPIView.as_view(), name='list product colletions'),
    path('destroyproduct/<int:pk>/', ProductDestroyAPIView.as_view(), name='Destroy product'),
    path('create/', ProductCreateView.as_view(), name='create colletions'),
    path('updateProduct/<int:pk>/', ProductUpdateApiView.as_view(),name='Update Product'),

    path('createtype/', TypeProductCreateView.as_view(), name='create type product'),
    path('destroytypeProduct/<int:pk>/', TypeProductDestroyAPIView.as_view(), name='Destroy type product'),
    path('listType/', TypeProductListView.as_view(), name='list type product'),
    path('typeProductFilter/', TypeProductFilterAdminAPIView.as_view(), name='filter Type Product Admin'),

    path('config/',CreacionParametrosAPIView.as_view(), name='config params'),
    path('config/destroy/', EliminacionParametrosAPIView.as_view(), name='destroy_config_params'),
    path('config/calculo/',PrecioSugeridoAPIView.as_view(),name='calculo de valor '),
    path('config/retrive/',ConfigProductoRetrieveAPIView.as_view(),name='see config params')

   
]
