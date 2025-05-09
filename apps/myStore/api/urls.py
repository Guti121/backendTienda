# urls.py
from django.urls import path

from apps.myStore.api.company.views.viewsCompany import CompanyCreateAPIView, CompanyDestroyAPIView, CompanyRetrieveAPIView, CompanyUpdateAPIView
from apps.myStore.api.qrCode import GenerarQRView, LeerQRView

urlpatterns = [

    #Codigo Qr para unir usuario a una compañia
    path('generar_qr/',GenerarQRView.as_view(), name='generar_qr'),
    path('validar_qr/',LeerQRView().as_view(), name='validar_qr'),

    #Urls relacionados con la tabla company
    path('createCompany/',CompanyCreateAPIView.as_view(), name='Create Company'),
    path('retrieveCompany/',CompanyRetrieveAPIView.as_view(),name='Retrieve Company'),
    path('destroyCompany/',CompanyDestroyAPIView.as_view(),name='Destroy Company'),
    path('updateCompany/',CompanyUpdateAPIView.as_view(),name='update Company')

]
