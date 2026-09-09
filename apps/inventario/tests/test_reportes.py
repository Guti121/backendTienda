from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_company, make_product, make_user
from apps.colletion.models import ProductModel
from apps.inventario.models import ReporteVentasDiario, ReporteVentasMensual
from apps.inventario.tasks import (
    generar_reporte_ventas_dia,
    generar_reporte_ventas_mes,
)
from apps.shoppingcart.models import Factura, FacturaDetalle


def make_venta(company, creador, producto, cantidad):
    """Crea una Factura de una línea. FacturaDetalle.save() congela el snapshot
    del producto; subtotal se pasa a mano (no lo calcula el modelo)."""
    factura = Factura.objects.create(
        total=Decimal(producto.valor) * cantidad, tienda=company, creado_por=creador,
    )
    FacturaDetalle.objects.create(
        factura=factura, producto=producto, cantidad=cantidad,
        subtotal=Decimal(producto.valor) * cantidad,
        valor_und=0, valor_mayor_und=0, valor_con_CF=0,  # los reescribe save()
        tienda=company, creado_por=creador,
    )
    return factura


class ReporteDiarioTaskTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company(
            nombre="tiendauno", email="uno@test.com", nit="900001")
        self.otra, self.otro_creador = make_company(
            nombre="tiendados", email="dos@test.com", nit="900002")
        self.prod = make_product(self.company, self.creador, valor="1000")

    def test_agrega_ventas_de_la_tienda(self):
        make_venta(self.company, self.creador, self.prod, 3)
        make_venta(self.company, self.creador, self.prod, 2)

        generar_reporte_ventas_dia()

        rep = ReporteVentasDiario.objects.get(tienda=self.company, fecha=date.today())
        self.assertEqual(rep.productos_vendidos, 5)
        self.assertEqual(rep.total_subtotal, Decimal("5000"))
        self.assertEqual(rep.facturas_total, 2)

    def test_no_crea_fila_en_cero(self):
        make_venta(self.company, self.creador, self.prod, 1)

        generar_reporte_ventas_dia()

        # La tienda sin ventas no tiene reporte.
        self.assertFalse(
            ReporteVentasDiario.objects.filter(tienda=self.otra).exists()
        )

    def test_es_idempotente(self):
        make_venta(self.company, self.creador, self.prod, 4)

        generar_reporte_ventas_dia()
        generar_reporte_ventas_dia()

        self.assertEqual(
            ReporteVentasDiario.objects.filter(tienda=self.company).count(), 1
        )

    def test_borra_reporte_si_el_dia_se_queda_sin_ventas(self):
        make_venta(self.company, self.creador, self.prod, 1)
        generar_reporte_ventas_dia()
        self.assertTrue(ReporteVentasDiario.objects.filter(tienda=self.company).exists())

        FacturaDetalle.objects.all().delete()
        generar_reporte_ventas_dia()

        self.assertFalse(
            ReporteVentasDiario.objects.filter(tienda=self.company).exists()
        )

    def test_signal_de_borrado_elimina_la_fila_vacia(self):
        factura = make_venta(self.company, self.creador, self.prod, 1)
        generar_reporte_ventas_dia()
        self.assertTrue(ReporteVentasDiario.objects.filter(tienda=self.company).exists())

        # transaction.on_commit no corre solo dentro de TestCase.
        with self.captureOnCommitCallbacks(execute=True):
            factura.detalles.all().delete()

        self.assertFalse(
            ReporteVentasDiario.objects.filter(tienda=self.company, fecha=date.today()).exists()
        )


class ReporteMensualTaskTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company(
            nombre="tiendauno", email="uno@test.com", nit="900001")
        self.otra, _ = make_company(
            nombre="tiendados", email="dos@test.com", nit="900002")
        # Un día del mes anterior.
        primero_este_mes = date.today().replace(day=1)
        self.dia_mes_pasado = primero_este_mes - timedelta(days=1)
        self.primer_dia_mes_pasado = self.dia_mes_pasado.replace(day=1)

    def test_suma_los_diarios_del_mes_anterior(self):
        for subtotal, prods in ((Decimal("1000"), 2), (Decimal("3000"), 5)):
            ReporteVentasDiario.objects.create(
                tienda=self.company,
                fecha=self.dia_mes_pasado,
                productos_vendidos=prods,
                total_subtotal=subtotal,
                facturas_total=1,
            )

        generar_reporte_ventas_mes()

        rep = ReporteVentasMensual.objects.get(
            tienda=self.company, fecha=self.primer_dia_mes_pasado)
        self.assertEqual(rep.productos_vendidos, 7)
        self.assertEqual(rep.total_subtotal, Decimal("4000"))
        self.assertEqual(rep.facturas_total, 2)

    def test_no_crea_mensual_sin_diarios(self):
        ReporteVentasDiario.objects.create(
            tienda=self.company, fecha=self.dia_mes_pasado,
            productos_vendidos=1, total_subtotal=Decimal("100"), facturas_total=1,
        )

        generar_reporte_ventas_mes()

        self.assertFalse(
            ReporteVentasMensual.objects.filter(tienda=self.otra).exists()
        )


class InventarioEndpointsTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company(
            nombre="tiendauno", email="uno@test.com", nit="900001")
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_listado_diario_es_de_la_tienda_y_paginado(self):
        ReporteVentasDiario.objects.create(
            tienda=self.company, fecha=date.today(),
            productos_vendidos=3, total_subtotal=Decimal("900"), facturas_total=1,
        )
        otra, _ = make_company(nombre="tiendados", email="dos@test.com", nit="900002")
        ReporteVentasDiario.objects.create(
            tienda=otra, fecha=date.today(),
            productos_vendidos=9, total_subtotal=Decimal("9000"), facturas_total=1,
        )

        r = self.client.get("/inventario/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("results", r.data)  # respuesta paginada
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["productos_vendidos"], 3)

    def test_listado_diario_filtra_por_mes_y_anio(self):
        hoy = date.today()
        viejo = (hoy.replace(day=1) - timedelta(days=40))
        ReporteVentasDiario.objects.create(
            tienda=self.company, fecha=hoy, productos_vendidos=1,
            total_subtotal=Decimal("1"), facturas_total=1)
        ReporteVentasDiario.objects.create(
            tienda=self.company, fecha=viejo, productos_vendidos=2,
            total_subtotal=Decimal("2"), facturas_total=1)

        r = self.client.get(f"/inventario/?month={hoy.month}&year={hoy.year}")
        self.assertEqual(r.data["count"], 1)

    def test_otros_roles_no_pueden(self):
        admin = make_user("invadmin", tipo=TipoUsuario.ADMIN, company=self.company)
        ca = APIClient()
        ca.force_authenticate(user=admin)
        self.assertEqual(ca.get("/inventario/").status_code, 403)

    def test_resumen_valida_mes_y_anio(self):
        self.assertEqual(self.client.get("/inventario/resumen/?month=13").status_code, 400)
        self.assertEqual(self.client.get("/inventario/resumen/?year=1990").status_code, 400)
        self.assertEqual(self.client.get("/inventario/resumen/").status_code, 200)

    def test_productos_solo_cuenta_disponibles(self):
        make_product(self.company, self.creador, nombre="Visible",
                     stock=10, valor="100", valor_mayor="60")
        oculto = make_product(self.company, self.creador, nombre="Oculto",
                              stock=10, valor="100", valor_mayor="60")
        ProductModel.objects.filter(pk=oculto.pk).update(disponible=False)

        for method in (self.client.get, self.client.post):
            r = method("/inventario/productos/")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["total_unidades_disponibles"], 10)
            self.assertEqual(Decimal(str(r.data["total_precio_venta"])), Decimal("1000"))
