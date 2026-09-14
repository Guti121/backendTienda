from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_company, make_user, png_file
from apps.myStore.models import Company


class CompanyCreateTest(TestCase):
    def test_creator_user_es_readonly(self):
        # El creador se toma del usuario autenticado, no del body.
        otro = make_user("otro", tipo=TipoUsuario.CLIENTE)
        fundador = make_user("fundador", tipo=TipoUsuario.CLIENTE)
        c = APIClient()
        c.force_authenticate(user=fundador)
        r = c.post("/store/createCompany/", {
            "nit": "999888", "company": "Nueva", "name": "nuevatienda",
            "phone": "1", "email": "nueva@test.com", "direction": "d",
            "municipality": "m", "creator_user": otro.id, "url_logo": png_file(),
        }, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        company = Company.objects.get(name="nuevatienda")
        self.assertEqual(company.creator_user_id, fundador.id)

    def test_cliente_pasa_a_creator_al_crear_empresa(self):
        fundador = make_user("fundador2", tipo=TipoUsuario.CLIENTE)
        c = APIClient()
        c.force_authenticate(user=fundador)
        r = c.post("/store/createCompany/", {
            "nit": "111222", "company": "Otra", "name": "otratienda",
            "phone": "1", "email": "otra@test.com", "direction": "d",
            "municipality": "m", "url_logo": png_file(),
        }, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        fundador.profile.refresh_from_db()
        self.assertEqual(fundador.profile.tipo_usuario, TipoUsuario.CREATOR)

    def test_url_logo_es_opcional(self):
        # Crear la tienda no debería bloquearse por no tener un logo a mano.
        fundador = make_user("fundador3", tipo=TipoUsuario.CLIENTE)
        c = APIClient()
        c.force_authenticate(user=fundador)
        r = c.post("/store/createCompany/", {
            "nit": "333444", "company": "SinLogo", "name": "sinlogotienda",
            "phone": "1", "email": "sinlogo@test.com", "direction": "d",
            "municipality": "m",
        }, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        company = Company.objects.get(name="sinlogotienda")
        self.assertFalse(company.url_logo)
