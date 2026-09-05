from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.tests.factories import make_company, make_product, make_tipo
from apps.colletion.models import ProductModel
from apps.shoppingcart.models import Factura, FacturaDetalle


class FacturaCreateTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def _venta(self, producto, cantidad):
        return self.client.post(
            "/facturas/create/",
            {"detalles": [{"producto": producto.id, "cantidad": cantidad}]},
            format="json",
        )

    def test_venta_ok_descuenta_stock(self):
        p = make_product(self.company, self.creador, stock=10, tipo=self.tipo)
        r = self._venta(p, 3)
        self.assertEqual(r.status_code, 201, r.data)
        p.refresh_from_db()
        self.assertEqual(p.unidades_disponibles, 7)
        self.assertTrue(p.disponible)
        self.assertEqual(Factura.objects.count(), 1)
        self.assertEqual(FacturaDetalle.objects.count(), 1)

    def test_venta_exacta_marca_no_disponible(self):
        p = make_product(self.company, self.creador, stock=5, tipo=self.tipo)
        self.assertEqual(self._venta(p, 5).status_code, 201)
        p.refresh_from_db()
        self.assertEqual(p.unidades_disponibles, 0)
        self.assertFalse(p.disponible)

    def test_sobreventa_devuelve_400_con_rollback(self):
        p = make_product(self.company, self.creador, stock=2, tipo=self.tipo)
        r = self._venta(p, 5)
        self.assertEqual(r.status_code, 400, r.data)
        p.refresh_from_db()
        self.assertEqual(p.unidades_disponibles, 2)  # sin cambios
        self.assertEqual(Factura.objects.count(), 0)

    def test_carrito_vacio_devuelve_400(self):
        r = self.client.post("/facturas/create/", {"detalles": []}, format="json")
        self.assertEqual(r.status_code, 400, r.data)

    def test_lineas_repetidas_del_mismo_producto_se_agrupan(self):
        p = make_product(self.company, self.creador, stock=4, tipo=self.tipo)
        r = self.client.post("/facturas/create/", {"detalles": [
            {"producto": p.id, "cantidad": 2},
            {"producto": p.id, "cantidad": 3},
        ]}, format="json")
        self.assertEqual(r.status_code, 400, r.data)  # 2+3 > 4
        p.refresh_from_db()
        self.assertEqual(p.unidades_disponibles, 4)


class FacturaListTotalesTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_totales_no_se_inflan_por_el_join(self):
        p = make_product(self.company, self.creador, stock=100, valor="1000")
        for cant in (3, 2):  # total 5000, 5 uds
            self.client.post("/facturas/create/",
                             {"detalles": [{"producto": p.id, "cantidad": cant}]}, format="json")

        r = self.client.get("/facturas/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["numero_de_facturas"], 2)
        self.assertEqual(r.data["total_cantidad_de_procuctos"], 5)
        digits = "".join(ch for ch in r.data["total_facturas"] if ch.isdigit())
        self.assertEqual(digits, "500000")  # 5000,00 COP
