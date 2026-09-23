

from apps.myStore.models import Company
from apps.catalogo.api.serializers.serializersCompany import CatalogoCompanySerializer
from rest_framework.generics import RetrieveAPIView
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from apps.catalogo.api.throttles import CatalogoAnonRateThrottle

class CompanyDetailView(RetrieveAPIView):
    """
    View to retrieve details of a company.
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [CatalogoAnonRateThrottle]
    serializer_class = CatalogoCompanySerializer

    def get_object(self):
        name_param = self.kwargs.get('name')
        if not name_param:
            raise ValidationError(detail="El parámetro 'name' es obligatorio.")
        
        company = get_object_or_404(Company, name__iexact=name_param)
        return company