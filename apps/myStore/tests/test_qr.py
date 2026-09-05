from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_company, make_user
from apps.myStore.api.qrCode import LeerQRView


class GenerarQRTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_rechaza_type_user_no_numerico(self):
        r = self.client.post("/store/generar_qr/", {"email": "n@test.com", "type_user": "abc"}, format="json")
        self.assertEqual(r.status_code, 400, r.data)

    def test_acepta_type_user_string_1(self):
        r = self.client.post("/store/generar_qr/", {"email": "n@test.com", "type_user": "1"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn("qr_base64", r.data)


class AddUserCompanyTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()

    def _token(self, email, type_user):
        t = AccessToken()
        t["company"] = str(self.company.id)
        t["email"] = email
        t["type_user"] = type_user
        return str(t)

    def test_mapea_type_user_string(self):
        nuevo = make_user("nuevo", tipo=TipoUsuario.CLIENTE)
        ok = LeerQRView().add_user_company(nuevo.email, nuevo.email, self._token(nuevo.email, "1"))
        self.assertTrue(ok)
        nuevo.profile.refresh_from_db()
        self.assertEqual(nuevo.profile.tipo_usuario, "worker")
        self.assertEqual(nuevo.profile.company_id, self.company.id)

    def test_type_user_invalido_devuelve_false(self):
        nuevo = make_user("nuevo2", tipo=TipoUsuario.CLIENTE)
        self.assertFalse(
            LeerQRView().add_user_company(nuevo.email, nuevo.email, self._token(nuevo.email, "99"))
        )
        nuevo.profile.refresh_from_db()
        self.assertEqual(nuevo.profile.tipo_usuario, TipoUsuario.CLIENTE)
