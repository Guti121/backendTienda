from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.tests.factories import make_company, make_descuento, make_product, make_tipo
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

    def test_totales_enteros_y_borrado_repone_stock(self):
        a = make_product(self.company, self.creador, stock=10,
                         valor="1000", valor_mayor="600", tipo=self.tipo)
        b = make_product(self.company, self.creador, stock=10, nombre="Prod B",
                         valor="1500", valor_mayor="900", tipo=self.tipo)
        r = self.client.post("/facturas/create/", {"detalles": [
            {"producto": a.id, "cantidad": 2},
            {"producto": b.id, "cantidad": 1},
        ]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)

        f = Factura.objects.get()
        self.assertEqual(f.total, Decimal("3500"))  # 2*1000 + 1*1500, entero
        for d in f.detalles.all():
            self.assertEqual(d.subtotal, d.subtotal.to_integral_value())
            self.assertEqual(d.valor_und, d.valor_und.to_integral_value())

        r = self.client.delete(f"/facturas/destroy/{f.id}/")
        self.assertIn(r.status_code, (200, 204), getattr(r, "data", r))
        self.assertEqual(Factura.objects.count(), 0)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(a.unidades_disponibles, 10)  # repuesto
        self.assertEqual(b.unidades_disponibles, 10)


class FacturaConDescuentoTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def _venta(self, detalles, descuento_porcentaje=None):
        payload = {"detalles": detalles}
        if descuento_porcentaje is not None:
            payload["descuento_porcentaje"] = descuento_porcentaje
        return self.client.post("/facturas/create/", payload, format="json")

    def test_promo_de_producto_se_aplica_sola_sin_input_explicito(self):
        p = make_product(self.company, self.creador, valor="1000", tipo=self.tipo)
        make_descuento(p, self.creador, porcentaje="20")
        r = self._venta([{"producto": p.id, "cantidad": 2}])
        self.assertEqual(r.status_code, 201, r.data)
        f = Factura.objects.get()
        d = f.detalles.get()
        self.assertEqual(d.descuento_porcentaje, Decimal("20"))
        self.assertEqual(d.subtotal, Decimal("1600"))  # 2*1000*0.8
        self.assertEqual(f.subtotal, Decimal("1600"))
        self.assertEqual(f.total, Decimal("1600"))  # sin descuento general

    def test_descuento_general_de_factura_sin_promo_de_producto(self):
        p = make_product(self.company, self.creador, valor="1000", tipo=self.tipo)
        r = self._venta([{"producto": p.id, "cantidad": 2}], descuento_porcentaje="10")
        self.assertEqual(r.status_code, 201, r.data)
        f = Factura.objects.get()
        self.assertEqual(f.subtotal, Decimal("2000"))
        self.assertEqual(f.total, Decimal("1800"))  # 2000 * 0.9
        self.assertEqual(f.descuento_porcentaje, Decimal("10"))

    def test_override_por_linea_sin_promo(self):
        p = make_product(self.company, self.creador, valor="1000", tipo=self.tipo)
        r = self._venta([{"producto": p.id, "cantidad": 1, "descuento_porcentaje": "30"}])
        self.assertEqual(r.status_code, 201, r.data)
        d = Factura.objects.get().detalles.get()
        self.assertEqual(d.descuento_porcentaje, Decimal("30"))
        self.assertEqual(d.subtotal, Decimal("700"))

    def test_override_de_linea_gana_sobre_la_promo_del_producto(self):
        p = make_product(self.company, self.creador, valor="1000", tipo=self.tipo)
        make_descuento(p, self.creador, porcentaje="20")
        r = self._venta([{"producto": p.id, "cantidad": 1, "descuento_porcentaje": "5"}])
        self.assertEqual(r.status_code, 201, r.data)
        d = Factura.objects.get().detalles.get()
        self.assertEqual(d.descuento_porcentaje, Decimal("5"))  # no 20
        self.assertEqual(d.subtotal, Decimal("950"))

    def test_cero_explicito_anula_la_promo_de_esa_linea(self):
        p = make_product(self.company, self.creador, valor="1000", tipo=self.tipo)
        make_descuento(p, self.creador, porcentaje="20")
        r = self._venta([{"producto": p.id, "cantidad": 1, "descuento_porcentaje": "0"}])
        self.assertEqual(r.status_code, 201, r.data)
        d = Factura.objects.get().detalles.get()
        self.assertEqual(d.descuento_porcentaje, Decimal("0"))
        self.assertEqual(d.subtotal, Decimal("1000"))

    def test_promo_de_producto_y_descuento_general_combinados(self):
        p = make_product(self.company, self.creador, valor="1000", tipo=self.tipo)
        make_descuento(p, self.creador, porcentaje="10")
        r = self._venta([{"producto": p.id, "cantidad": 1}], descuento_porcentaje="10")
        self.assertEqual(r.status_code, 201, r.data)
        f = Factura.objects.get()
        # línea: 1000 * 0.9 = 900 (subtotal). factura: 900 * 0.9 = 810.
        self.assertEqual(f.subtotal, Decimal("900"))
        self.assertEqual(f.total, Decimal("810"))

    def test_porcentaje_fuera_de_rango_400(self):
        p = make_product(self.company, self.creador, valor="1000", tipo=self.tipo)
        r = self._venta([{"producto": p.id, "cantidad": 1}], descuento_porcentaje="150")
        self.assertEqual(r.status_code, 400, r.data)

        r = self._venta([{"producto": p.id, "cantidad": 1, "descuento_porcentaje": "-5"}])
        self.assertEqual(r.status_code, 400, r.data)


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

    def test_filtro_por_mes_y_por_fecha(self):
        # El filtro usa rangos [inicio, fin), no fecha__year/__month (que en MySQL
        # sin tablas de timezone devuelven vacío).
        import datetime as dt
        p = make_product(self.company, self.creador, stock=20, valor="1000")
        self.client.post("/facturas/create/",
                         {"detalles": [{"producto": p.id, "cantidad": 1}]}, format="json")
        hoy = dt.date.today()

        r = self.client.get("/facturas/", {"month": hoy.month, "year": hoy.year})
        self.assertEqual(r.data["numero_de_facturas"], 1, r.data)

        r = self.client.get("/facturas/", {"date": hoy.isoformat()})
        self.assertEqual(r.data["numero_de_facturas"], 1, r.data)

        # Un mes sin facturas -> 0
        otro = hoy.replace(year=hoy.year - 1)
        r = self.client.get("/facturas/", {"month": otro.month, "year": otro.year})
        self.assertEqual(r.data["numero_de_facturas"], 0, r.data)
