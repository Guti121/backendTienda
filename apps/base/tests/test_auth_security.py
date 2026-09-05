from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.models import CustomUser
from apps.base.tests.factories import make_company


class AuthSecurityTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()

    def test_endpoint_protegido_sin_auth_devuelve_401(self):
        # DEFAULT_PERMISSION_CLASSES = IsAuthenticated
        r = APIClient().post("/facturas/create/", {"detalles": []}, format="json")
        self.assertEqual(r.status_code, 401, r.data)

    def test_registro_sigue_publico(self):
        r = APIClient().post("/register/", {
            "username": "publico", "email": "publico@test.com",
            "first_name": "Pu", "last_name": "Blico",
            "password": "clave12345", "password_verify": "clave12345",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def test_catalogo_publico_accesible_sin_auth(self):
        r = APIClient().get(f"/catalogo/company/{self.company.name}")
        self.assertEqual(r.status_code, 200, r.data)


class CompanyOwnerCacheTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()

    def test_company_owner_cachea_el_perfil(self):
        from Tienda_Virtual.globalFunctions import company_owner
        u = CustomUser.objects.get(pk=self.creador.pk)  # instancia fresca, sin cache
        # 3 llamadas -> 2 queries (perfil + company), cacheadas en la instancia.
        # Antes: 2 queries POR llamada (get_object_or_404).
        with self.assertNumQueries(2):
            company_owner(u)
            company_owner(u)
            company_owner(u)
