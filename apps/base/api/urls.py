# urls.py
from django.urls import path

from apps.base.api.user.viewsUserCreateType import  ListUserCompanyAPIView, UpdateUserCompanyAPIView


urlpatterns = [

    #List owner workers
    path('listUsersCompany/',ListUserCompanyAPIView.as_view(), name='List User Company'),
    path('DestroyUsersCompany/<int:pk>/',UpdateUserCompanyAPIView.as_view(), name='Destroy User Company'),

   

]
