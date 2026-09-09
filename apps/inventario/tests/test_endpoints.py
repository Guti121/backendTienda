from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_company, make_product, make_user
from apps.shoppingcart.models import Factura, FacturaDetalle


def make_venta(company, creador, producto, cantidad, cuando=None):
    """Factura de una línea. FacturaDetalle.save() congela el snapshot del
    producto; subtotal se pasa a mano. `cuando` (aware) fuerza creado_en
    (auto_now_add) vía UPDATE posterior."""
    factura = Factura.objects.create(
        total=Decimal(producto.valor) * cantidad, tienda=company, creado_por=creador,
    )
    det = FacturaDetalle.objects.create(
        factura=factura, producto=producto, cantidad=cantidad,
        subtotal=Decimal(producto.valor) * cantidad,
        valor_und=0, valor_mayor_und=0, valor_con_CF=0,
        tienda=company, creado_por=creador,
    )
    if cuando is not None:
        FacturaDetalle.objects.filter(pk=det.pk).update(creado_en=cuando)
        Factura.objects.filter(pk=factura.pk).update(fecha=cuando)
    return factura


class InventarioDiarioTest(TestCase):
    def setUp(self):
        cache.clear()
        self.company, self.creador = make_company(
            nombre="tiendauno", email="uno@test.com", nit="900001")
        self.prod = make_product(self.company, self.creador, valor="1000")
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_agrega_por_dia_y_shape_paginado(self):
        make_venta(self.company, self.creador, self.prod, 3)
        make_venta(self.company, self.creador, self.prod, 2)
        hoy = date.today()

        r = self.client.get(f"/inventario/?month={hoy.month}&year={hoy.year}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("results", r.data)
        self.assertEqual(r.data["count"], 1)
        fila = r.data["results"][0]
        self.assertEqual(fila["fecha"], hoy.isoformat())
        self.assertEqual(fila["facturas_total"], 2)
        self.assertEqual(fila["productos_vendidos"], 5)
        self.assertEqual(Decimal(str(fila["total_subtotal"])), Decimal("5000"))

    def test_agrupa_por_dia_local_no_utc(self):
        # Venta a las 23:30 hora local de hoy: debe caer en HOY, no en mañana
        # (en UTC serían las 04:30 del día siguiente).
        tz = timezone.get_current_timezone()
        hoy = date.today()
        tarde = timezone.make_aware(datetime.combine(hoy, time(23, 30)), tz)
        make_venta(self.company, self.creador, self.prod, 1, cuando=tarde)

        r = self.client.get(f"/inventario/?month={hoy.month}&year={hoy.year}")
        self.assertEqual([f["fecha"] for f in r.data["results"]], [hoy.isoformat()])

    def test_dias_sin_ventas_no_aparecen(self):
        make_venta(self.company, self.creador, self.prod, 1)
        hoy = date.today()
        r = self.client.get(f"/inventario/?month={hoy.month}&year={hoy.year}")
        self.assertEqual(r.data["count"], 1)  # solo el día de la venta

    def test_aislamiento_por_tienda(self):
        otra, otro = make_company(nombre="tiendados", email="d@test.com", nit="900002")
        pot = make_product(otra, otro, valor="1000")
        make_venta(otra, otro, pot, 9)
        make_venta(self.company, self.creador, self.prod, 1)
        hoy = date.today()

        r = self.client.get(f"/inventario/?month={hoy.month}&year={hoy.year}")
        self.assertEqual(r.data["results"][0]["productos_vendidos"], 1)

    def test_otros_roles_403(self):
        admin = make_user("invadmin", tipo=TipoUsuario.ADMIN, company=self.company)
        ca = APIClient()
        ca.force_authenticate(user=admin)
        self.assertEqual(ca.get("/inventario/").status_code, 403)

    def test_mes_o_anio_invalido_400(self):
        self.assertEqual(self.client.get("/inventario/?month=13&year=2026").status_code, 400)
        self.assertEqual(self.client.get("/inventario/?month=2&year=1990").status_code, 400)
        self.assertEqual(self.client.get("/inventario/?month=abc&year=2026").status_code, 400)


class InventarioResumenYMensualTest(TestCase):
    def setUp(self):
        cache.clear()
        self.company, self.creador = make_company(
            nombre="tiendauno", email="uno@test.com", nit="900001")
        self.prod = make_product(self.company, self.creador, valor="1000",
                                 valor_mayor="600")
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_resumen_agrega_el_mes(self):
        make_venta(self.company, self.creador, self.prod, 4)
        hoy = date.today()
        r = self.client.get(f"/inventario/resumen/?month={hoy.month}&year={hoy.year}")
        self.assertEqual(r.status_code, 200)
        res = r.data["resumen"]
        self.assertEqual(res["productos_vendidos"], 4)
        self.assertEqual(Decimal(str(res["total_ventas"])), Decimal("4000"))

    def test_resumen_valida(self):
        self.assertEqual(self.client.get("/inventario/resumen/?month=13").status_code, 400)
        self.assertEqual(self.client.get("/inventario/resumen/?year=1990").status_code, 400)
        self.assertEqual(self.client.get("/inventario/resumen/").status_code, 200)

    def test_mensual_lista_meses_con_ventas(self):
        make_venta(self.company, self.creador, self.prod, 2)
        r = self.client.get("/inventario/mensual/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)
        primero_mes = date.today().replace(day=1).isoformat()
        self.assertEqual(r.data["results"][0]["fecha"], primero_mes)


class InventarioCacheTest(TestCase):
    def setUp(self):
        cache.clear()
        self.company, self.creador = make_company(
            nombre="tiendauno", email="uno@test.com", nit="900001")
        self.prod = make_product(self.company, self.creador, valor="1000")
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)
        self.hoy = date.today()

    def _get(self):
        return self.client.get(
            f"/inventario/resumen/?month={self.hoy.month}&year={self.hoy.year}")

    @staticmethod
    def _agg_queries(ctx):
        return [q for q in ctx.captured_queries
                if "facturadetalle" in q["sql"].lower()]

    def test_segunda_lectura_desde_cache_y_bump_invalida(self):
        make_venta(self.company, self.creador, self.prod, 1)

        with CaptureQueriesContext(connection) as c1:
            r1 = self._get()
        self.assertEqual(r1.data["resumen"]["productos_vendidos"], 1)
        self.assertTrue(self._agg_queries(c1))  # la 1ª vez sí agrega

        with CaptureQueriesContext(connection) as c2:
            self._get()
        self.assertEqual(self._agg_queries(c2), [])  # la 2ª, de caché

        # Nueva venta -> el signal (on_commit) invalida -> la lectura refleja.
        with self.captureOnCommitCallbacks(execute=True):
            make_venta(self.company, self.creador, self.prod, 5)

        r3 = self._get()
        self.assertEqual(r3.data["resumen"]["productos_vendidos"], 6)


class InventarioProductosTest(TestCase):
    def setUp(self):
        cache.clear()
        self.company, self.creador = make_company(
            nombre="tiendauno", email="uno@test.com", nit="900001")
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_solo_cuenta_disponibles(self):
        from apps.colletion.models import ProductModel
        make_product(self.company, self.creador, nombre="Visible",
                     stock=10, valor="100", valor_mayor="60")
        oculto = make_product(self.company, self.creador, nombre="Oculto",
                              stock=10, valor="100", valor_mayor="60")
        ProductModel.objects.filter(pk=oculto.pk).update(disponible=False)

        for call in (self.client.get, self.client.post):
            r = call("/inventario/productos/")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["total_unidades_disponibles"], 10)
            self.assertEqual(Decimal(str(r.data["total_precio_venta"])), Decimal("1000"))
