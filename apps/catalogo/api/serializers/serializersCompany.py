from apps.colletion.api.serializers.serializer import _abs_media
from apps.myStore.models import Company
from rest_framework import serializers


class CatalogoCompanySerializer(serializers.ModelSerializer):
    """Datos públicos de la tienda para el catálogo web, incluida la
    personalización (fuente, frase, anuncio, banner)."""

    catalog_banner = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = ['id', 'name', 'company', 'url_logo', 'phone', 'email',
                  'direction', 'municipality',
                  'catalog_font', 'catalog_tagline', 'catalog_announcement',
                  'catalog_banner']

    def get_catalog_banner(self, obj):
        # URL absoluta: FileField.url es relativa y catalog-web corre en otro origen.
        return _abs_media(self, obj.catalog_banner.url) if obj.catalog_banner else None
