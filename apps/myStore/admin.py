from django.contrib import admin

from apps.myStore.models import Company, Details_company

# Register your models here.
admin.site.register(Company)
admin.site.register(Details_company)