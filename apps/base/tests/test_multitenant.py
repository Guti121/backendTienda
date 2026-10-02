"""Aislamiento multi-tenant: un usuario de la empresa A no puede leer ni mutar
objetos de la empresa B por ningún endpoint que reciba un <pk>.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_caja, make_company, make_product, make_tipo, make_user
from apps.colletion.models import (Bar_codeModel, Config_ProductModel, ProductModel,
                                   TypeProductModel)
from apps.shoppingcart.models import Factura, FacturaDetalle


class MultiTenantIsolationTest(TestCase):
    def setUp(self):
        # Empresa A
        self.A, self.ana = make_company("tiendaa", "a@t.com", "900A")
        self.tpA = make_tipo(self.A, self.ana, "TipoA")
        self.pA = make_product(self.A, self.ana, "ProdA", stock=10, tipo=self.tpA)
        make_caja(self.A, self.ana)
        # Empresa B
        self.B, self.beto = make_company("tiendab", "b@t.com", "900B")
        self.tpB = make_tipo(self.B, self.beto, "TipoB")
        self.pB = make_product(self.B, self.beto, "ProdB", stock=10, tipo=self.tpB)
        # En TestCase el on_commit del save() no dispara la tarea; generamos el
        # código de barras a mano (síncrono, idempotente).
        self.pA.crear_codigo_barras()
        self.pB.crear_codigo_barras()
        Config_ProductModel.objects.create(
            tienda=self.B, creado_por=self.beto, costos_fijos=Decimal("1000"),
            margen_ganancia=Decimal("1"), promedio_productos_vendidos=10)
        self.fB = Factura.objects.create(subtotal=Decimal("100"), total=Decimal("100"), tienda=self.B, creado_por=self.beto)
        FacturaDetalle.objects.create(factura=self.fB, producto=self.pB, cantidad=1,
                                      subtotal=Decimal("100"), tienda=self.B, creado_por=self.beto)
        self.workerB = make_user("wb", tipo=TipoUsuario.WORKER, company=self.B)

        self.ana_c = APIClient()
        self.ana_c.force_authenticate(self.ana)   # creator de A

    # ---- productos de B ----
    def test_A_no_ve_producto_de_B(self):
        self.assertEqual(self.ana_c.get(f"/productDetail/{self.pB.id}/").status_code, 404)

    def test_A_no_edita_producto_de_B(self):
        r = self.ana_c.patch(f"/updateProduct/{self.pB.id}/", {"nombre": "hack"}, format="json")
        self.pB.refresh_from_db()
        self.assertEqual(r.status_code, 404)
        self.assertNotEqual(self.pB.nombre.lower(), "hack")

    def test_A_no_borra_producto_de_B(self):
        r = self.ana_c.delete(f"/destroyproduct/{self.pB.id}/")
        self.assertIn(r.status_code, (400, 404))
        self.assertTrue(ProductModel.objects.filter(id=self.pB.id).exists())

    def test_A_no_ve_barcode_de_B(self):
        cbB = Bar_codeModel.objects.filter(tienda=self.B).first()
        self.assertIsNotNone(cbB)
        self.assertEqual(self.ana_c.get(f"/facturas/api/barcode/{self.pB.id}/").status_code, 404)

    def test_listados_de_A_no_incluyen_objetos_de_B(self):
        ids = {x["id"] for x in self.ana_c.get("/list/").data.get("results", [])}
        self.assertNotIn(self.pB.id, ids)
        tids = {x["id"] for x in self.ana_c.get("/listType/").data.get("results", [])}
        self.assertNotIn(self.tpB.id, tids)

    # ---- tipos de producto de B ----
    def test_A_no_borra_tipo_de_B(self):
        r = self.ana_c.delete(f"/destroytypeProduct/{self.tpB.id}/")
        self.assertIn(r.status_code, (400, 404))
        self.assertTrue(TypeProductModel.objects.filter(id=self.tpB.id).exists())

    # ---- facturas de B ----
    def test_A_no_ve_factura_de_B(self):
        self.assertEqual(self.ana_c.get(f"/facturas/{self.fB.id}/").status_code, 404)

    def test_A_no_borra_factura_de_B(self):
        r = self.ana_c.delete(f"/facturas/destroy/{self.fB.id}/")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Factura.objects.filter(id=self.fB.id).exists())

    def test_A_lista_solo_sus_facturas(self):
        Factura.objects.create(subtotal=Decimal("1"), total=Decimal("1"), tienda=self.A, creado_por=self.ana)
        r = self.ana_c.get("/facturas/")
        self.assertEqual(r.data["numero_de_facturas"], Factura.objects.filter(tienda=self.A).count())

    def test_A_no_factura_producto_de_B(self):
        stock0 = self.pB.unidades_disponibles
        r = self.ana_c.post("/facturas/create/",
                            {"detalles": [{"producto": self.pB.id, "cantidad": 1}]}, format="json")
        self.pB.refresh_from_db()
        self.assertIn(r.status_code, (400, 404))
        self.assertEqual(self.pB.unidades_disponibles, stock0)

    def test_A_no_lee_codigo_de_barras_de_B(self):
        codeB = Bar_codeModel.objects.filter(tienda=self.B).first().code
        r = self.ana_c.post("/facturas/codigo_de_barras_text/",
                            {"codigoBarras": codeB, "cantidad": 1}, format="json")
        self.assertFalse(r.status_code == 200 and "nombre" in r.data)

    # ---- usuarios / empresa de B ----
    def test_A_no_lista_usuarios_de_B(self):
        emails = {u["email"] for u in self.ana_c.get("/base/listUsersCompany/").data.get("results", [])}
        self.assertNotIn(self.beto.email, emails)
        self.assertNotIn(self.workerB.email, emails)

    def test_A_no_expulsa_usuario_de_B(self):
        r = self.ana_c.patch(f"/base/DestroyUsersCompany/{self.workerB.profile.id}/", {}, format="json")
        self.workerB.profile.refresh_from_db()
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.workerB.profile.company_id, self.B.id)
        self.assertEqual(self.workerB.profile.tipo_usuario, TipoUsuario.WORKER)

    def test_A_retrieve_company_es_la_suya(self):
        r = self.ana_c.get("/store/retrieveCompany/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "tiendaa")

    def test_A_update_company_no_toca_a_B(self):
        self.ana_c.patch("/store/updateCompany/", {"phone": "000"}, format="json")
        self.B.refresh_from_db()
        self.assertNotEqual(self.B.phone, "000")

    # ---- config de precios de B ----
    def test_A_config_retrieve_es_de_A_no_de_B(self):
        Config_ProductModel.objects.create(
            tienda=self.A, creado_por=self.ana, costos_fijos=Decimal("1"),
            margen_ganancia=Decimal("1"), promedio_productos_vendidos=1)
        r = self.ana_c.get("/config/retrive/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Config_ProductModel.objects.get(id=r.data["id"]).tienda_id, self.A.id)

    def test_A_config_destroy_no_borra_la_de_B(self):
        self.ana_c.delete("/config/destroy/")
        self.assertTrue(Config_ProductModel.objects.filter(tienda=self.B).exists())

    # ---- catálogo público cruzado ----
    def test_catalogo_de_B_no_expone_productos_de_A(self):
        c = APIClient()
        # producto de A publicable
        self.pA.publicar = True
        self.pA.save()
        r = c.get(f"/catalogo/product/tiendab/{self.pA.id}")
        self.assertEqual(r.status_code, 404)
        r = c.get("/catalogo/list/tiendab")
        nombres = {i["nombre"] for i in r.data.get("results", r.data)}
        self.assertNotIn(self.pA.nombre, nombres)
