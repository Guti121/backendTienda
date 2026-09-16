from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.base.tests.factories import make_company, make_descuento, make_product, make_tipo
from apps.colletion.models import DescuentoProducto


class DescuentoVigenteTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.p = make_product(self.company, self.creador)

    def test_vigente_dentro_de_la_ventana(self):
        d = make_descuento(self.p, self.creador, porcentaje="20", dias=7)
        self.assertTrue(d.vigente)

    def test_no_vigente_antes_de_empezar(self):
        d = make_descuento(self.p, self.creador, porcentaje="20", dias=7,
                            inicio=timezone.now() + timedelta(days=1))
        self.assertFalse(d.vigente)

    def test_no_vigente_despues_de_terminar(self):
        d = make_descuento(self.p, self.creador, porcentaje="20", dias=1,
                            inicio=timezone.now() - timedelta(days=5))
        self.assertFalse(d.vigente)

    def test_no_vigente_si_inactivo_aunque_este_en_la_ventana(self):
        d = make_descuento(self.p, self.creador, porcentaje="20", dias=7, activo=False)
        self.assertFalse(d.vigente)


class SoloUnaPromoActivaTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.p = make_product(self.company, self.creador)

    def test_activar_una_desactiva_la_anterior(self):
        a = make_descuento(self.p, self.creador, porcentaje="10")
        b = make_descuento(self.p, self.creador, porcentaje="30")
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertFalse(a.activo)
        self.assertTrue(b.activo)

    def test_no_afecta_promos_de_otro_producto(self):
        otro = make_product(self.company, self.creador, nombre="Otro")
        a = make_descuento(self.p, self.creador, porcentaje="10")
        make_descuento(otro, self.creador, porcentaje="30")
        a.refresh_from_db()
        self.assertTrue(a.activo)


class DescuentoProductoAPITest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
        self.p = make_product(self.company, self.creador, tipo=self.tipo)
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def _payload(self, **over):
        now = timezone.now()
        payload = {
            "producto": self.p.id,
            "porcentaje": "15",
            "fecha_inicio": now.isoformat(),
            "fecha_fin": (now + timedelta(days=3)).isoformat(),
        }
        payload.update(over)
        return payload

    def test_crear_promo_ok(self):
        r = self.client.post("/descuentos/create/", self._payload(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(DescuentoProducto.objects.count(), 1)

    def test_fecha_fin_antes_de_inicio_400(self):
        now = timezone.now()
        r = self.client.post("/descuentos/create/", self._payload(
            fecha_inicio=now.isoformat(),
            fecha_fin=(now - timedelta(days=1)).isoformat(),
        ), format="json")
        self.assertEqual(r.status_code, 400)

    def test_porcentaje_fuera_de_rango_400(self):
        r = self.client.post("/descuentos/create/", self._payload(porcentaje="150"), format="json")
        self.assertEqual(r.status_code, 400)

    def test_no_se_puede_crear_promo_de_otra_tienda(self):
        otra_company, otro_creador = make_company(nombre="otratienda", email="otra@test.com", nit="900999")
        otro_producto = make_product(otra_company, otro_creador, nombre="Ajeno")
        r = self.client.post("/descuentos/create/", self._payload(producto=otro_producto.id), format="json")
        self.assertEqual(r.status_code, 400)

    def test_worker_no_puede_crear_promo(self):
        from apps.base.models import TipoUsuario
        from apps.base.tests.factories import make_user
        worker = make_user("wrk_desc", tipo=TipoUsuario.WORKER, company=self.company)
        wc = APIClient(); wc.force_authenticate(worker)
        r = wc.post("/descuentos/create/", self._payload(), format="json")
        self.assertEqual(r.status_code, 403)
