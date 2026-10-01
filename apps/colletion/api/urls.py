from django.urls import path
from apps.colletion.api.views.view_config_price import ConfigProductoRetrieveAPIView, CreacionParametrosAPIView, EliminacionParametrosAPIView, PrecioSugeridoAPIView
from apps.colletion.api.views.view_descuento import DescuentoProductoCreateView, DescuentoProductoDestroyView, DescuentoProductoListView, DescuentoProductoUpdateView
from apps.colletion.api.views.view_product import ProductCreateView,ProductDestroyAPIView,ListProductAPIView, ProductFilterAdminAPIView,ProductListFilterAPIView,ProductRetrieveAPIView, ProductUpdateApiView
from apps.colletion.api.views.view_typeproduct import TypeProductCreateView,TypeProductDestroyAPIView, TypeProductFilterAdminAPIView, TypeProductListView
from apps.colletion.api.views.view_category import CategoryCreateView, CategoryDestroyAPIView, CategoryFilterAdminAPIView, CategoryListView, CategoryUpdateAPIView

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

    path('createcategory/', CategoryCreateView.as_view(), name='create category'),
    path('destroycategory/<int:pk>/', CategoryDestroyAPIView.as_view(), name='destroy category'),
    path('listCategory/', CategoryListView.as_view(), name='list category'),
    path('categoryFilter/', CategoryFilterAdminAPIView.as_view(), name='filter category admin'),
    path('categoryUpdate/<int:pk>/', CategoryUpdateAPIView.as_view(), name='update category'),

    path('config/',CreacionParametrosAPIView.as_view(), name='config params'),
    path('config/destroy/', EliminacionParametrosAPIView.as_view(), name='destroy_config_params'),
    path('config/calculo/',PrecioSugeridoAPIView.as_view(),name='calculo de valor '),
    path('config/retrive/',ConfigProductoRetrieveAPIView.as_view(),name='see config params'),

    path('descuentos/create/', DescuentoProductoCreateView.as_view(), name='create descuento producto'),
    path('descuentos/list/', DescuentoProductoListView.as_view(), name='list descuentos producto'),
    path('descuentos/update/<int:pk>/', DescuentoProductoUpdateView.as_view(), name='update descuento producto'),
    path('descuentos/destroy/<int:pk>/', DescuentoProductoDestroyView.as_view(), name='destroy descuento producto'),
]
