from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_caja, make_company, make_product, make_tipo, make_user
from apps.shoppingcart.models import CajaModel, Factura


class CajaAbrirTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_abrir_caja_ok(self):
        r = self.client.post("/facturas/caja/abrir/", {"monto_apertura": "50000"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(CajaModel.objects.count(), 1)
        self.assertEqual(CajaModel.objects.get().monto_apertura, Decimal("50000"))

    def test_abrir_segunda_caja_mientras_hay_una_abierta_400(self):
        make_caja(self.company, self.creador, "0")
        r = self.client.post("/facturas/caja/abrir/", {"monto_apertura": "10000"}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(CajaModel.objects.count(), 1)

    def test_monto_apertura_negativo_400(self):
        r = self.client.post("/facturas/caja/abrir/", {"monto_apertura": "-1"}, format="json")
        self.assertEqual(r.status_code, 400, r.data)


class CajaFacturarEnforcementTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_facturar_sin_caja_abierta_400(self):
        p = make_product(self.company, self.creador, valor="1000", tipo=self.tipo)
        r = self.client.post(
            "/facturas/create/", {"detalles": [{"producto": p.id, "cantidad": 1}]}, format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("caja", str(r.data["error"]).lower())
        self.assertEqual(Factura.objects.count(), 0)

    def test_facturar_con_caja_abierta_queda_asociada(self):
        caja = make_caja(self.company, self.creador, "0")
        p = make_product(self.company, self.creador, valor="1000", tipo=self.tipo)
        r = self.client.post(
            "/facturas/create/", {"detalles": [{"producto": p.id, "cantidad": 1}]}, format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Factura.objects.get().caja_id, caja.id)


class MovimientoCajaTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_movimiento_sin_caja_abierta_404(self):
        r = self.client.post(
            "/facturas/caja/movimiento/",
            {"tipo": "ingreso", "monto": "5000", "motivo": "x"}, format="json",
        )
        self.assertEqual(r.status_code, 404, r.data)

    def test_registrar_ingreso_y_retiro(self):
        make_caja(self.company, self.creador, "0")
        r = self.client.post(
            "/facturas/caja/movimiento/",
            {"tipo": "ingreso", "monto": "20000", "motivo": "Vuelto inicial"}, format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.post(
            "/facturas/caja/movimiento/",
            {"tipo": "retiro", "monto": "15000", "motivo": "Domicilio"}, format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)

    def test_monto_cero_o_negativo_400(self):
        make_caja(self.company, self.creador, "0")
        r = self.client.post(
            "/facturas/caja/movimiento/",
            {"tipo": "ingreso", "monto": "0", "motivo": "x"}, format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)


class CajaResumenYCerrarTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def _venta(self, metodo_pago, valor="1000"):
        p = make_product(self.company, self.creador, valor=valor, tipo=self.tipo)
        return self.client.post(
            "/facturas/create/",
            {"detalles": [{"producto": p.id, "cantidad": 1}], "metodo_pago": metodo_pago},
            format="json",
        )

    def test_resumen_solo_suma_efectivo_al_esperado(self):
        make_caja(self.company, self.creador, "50000")
        self._venta("efectivo", "1000")
        self._venta("datafono", "9000")  # no debe sumar al esperado

        r = self.client.get("/facturas/caja/resumen/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(r.data["ventas_efectivo"]), Decimal("1000"))
        self.assertEqual(Decimal(r.data["esperado_en_caja"]), Decimal("51000"))  # 50000 + 1000
        self.assertEqual(r.data["numero_de_facturas"], 2)

    def test_ingresos_y_retiros_afectan_el_esperado(self):
        make_caja(self.company, self.creador, "10000")
        self.client.post(
            "/facturas/caja/movimiento/",
            {"tipo": "ingreso", "monto": "5000", "motivo": "x"}, format="json",
        )
        self.client.post(
            "/facturas/caja/movimiento/",
            {"tipo": "retiro", "monto": "2000", "motivo": "y"}, format="json",
        )
        r = self.client.get("/facturas/caja/resumen/")
        self.assertEqual(Decimal(r.data["esperado_en_caja"]), Decimal("13000"))  # 10000+5000-2000

    def test_cerrar_caja_calcula_diferencia(self):
        make_caja(self.company, self.creador, "10000")
        self._venta("efectivo", "5000")
        # esperado = 15000; declara 14000 -> diferencia -1000 (falta plata)
        r = self.client.post(
            "/facturas/caja/cerrar/",
            {"monto_cierre_declarado": "14000", "nota_cierre": "faltó"}, format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        caja = CajaModel.objects.get()
        self.assertIsNotNone(caja.cerrada_en)
        self.assertEqual(caja.monto_cierre_esperado, Decimal("15000"))
        self.assertEqual(caja.diferencia, Decimal("-1000"))
        self.assertEqual(caja.cerrada_por_id, self.creador.id)

    def test_cerrar_caja_ya_cerrada_404(self):
        make_caja(self.company, self.creador, "0")
        self.client.post("/facturas/caja/cerrar/", {"monto_cierre_declarado": "0"}, format="json")
        r = self.client.post("/facturas/caja/cerrar/", {"monto_cierre_declarado": "0"}, format="json")
        self.assertEqual(r.status_code, 404, r.data)

    def test_no_se_puede_facturar_tras_cerrar_sin_abrir_otra(self):
        make_caja(self.company, self.creador, "0")
        self.client.post("/facturas/caja/cerrar/", {"monto_cierre_declarado": "0"}, format="json")
        p = make_product(self.company, self.creador, valor="1000", tipo=self.tipo)
        r = self.client.post(
            "/facturas/create/", {"detalles": [{"producto": p.id, "cantidad": 1}]}, format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)


class CajaMultiTenantTest(TestCase):
    def setUp(self):
        self.A, self.ana = make_company("tiendacajaa", "cajaa@t.com", "900CA")
        self.B, self.beto = make_company("tiendacajab", "cajab@t.com", "900CB")
        self.caja_b = make_caja(self.B, self.beto, "0")
        self.ana_c = APIClient()
        self.ana_c.force_authenticate(self.ana)

    def test_A_no_ve_caja_actual_de_B(self):
        r = self.ana_c.get("/facturas/caja/actual/")
        self.assertEqual(r.status_code, 404, r.data)

    def test_A_puede_abrir_su_propia_caja_aunque_B_tenga_una_abierta(self):
        r = self.ana_c.post("/facturas/caja/abrir/", {"monto_apertura": "0"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def test_historial_requiere_admin_o_creator(self):
        worker = make_user("wk_caja", tipo=TipoUsuario.WORKER, company=self.B)
        wc = APIClient(); wc.force_authenticate(worker)
        r = wc.get("/facturas/caja/historial/")
        self.assertEqual(r.status_code, 403, r.data)
