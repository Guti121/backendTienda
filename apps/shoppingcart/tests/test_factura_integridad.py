"""Integridad de facturas: borrado atómico, snapshot inmutable, PROTECT en
creado_por, y bloqueo de borrado de producto con ventas.
"""
from decimal import Decimal

from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_caja, make_company, make_descuento, make_product, make_tipo, make_user
from apps.colletion.models import ProductModel
from apps.shoppingcart.models import Factura, FacturaDetalle


class BorrarFacturaTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
        make_caja(self.company, self.creador)
        self.worker = make_user("wrk", tipo=TipoUsuario.WORKER, company=self.company)
        self.wc = APIClient(); self.wc.force_authenticate(self.worker)   # crea
        self.cc = APIClient(); self.cc.force_authenticate(self.creador)  # borra

    def _factura(self, *lineas):
        r = self.wc.post("/facturas/create/",
                         {"detalles": [{"producto": p.id, "cantidad": c} for p, c in lineas]},
                         format="json")
        assert r.status_code == 201, r.data
        return r.data["factura_id"]

    def test_borrar_factura_repone_stock_y_borra_detalles(self):
        p1 = make_product(self.company, self.creador, "P1", stock=10, tipo=self.tipo)
        p2 = make_product(self.company, self.creador, "P2", stock=10, tipo=self.tipo)
        fid = self._factura((p1, 3), (p2, 4))
        p1.refresh_from_db(); p2.refresh_from_db()
        self.assertEqual((p1.unidades_disponibles, p2.unidades_disponibles), (7, 6))

        r = self.cc.delete(f"/facturas/destroy/{fid}/")
        self.assertIn(r.status_code, (200, 204))
        p1.refresh_from_db(); p2.refresh_from_db()
        self.assertEqual((p1.unidades_disponibles, p2.unidades_disponibles), (10, 10))
        self.assertFalse(Factura.objects.filter(id=fid).exists())
        self.assertFalse(FacturaDetalle.objects.filter(factura_id=fid).exists())

    def test_stock_agotado_vuelve_a_disponible_al_anular(self):
        p = make_product(self.company, self.creador, "P", stock=5, tipo=self.tipo)
        fid = self._factura((p, 5))
        p.refresh_from_db()
        self.assertFalse(p.disponible)  # se agotó
        self.cc.delete(f"/facturas/destroy/{fid}/")
        p.refresh_from_db()
        self.assertTrue(p.disponible and p.unidades_disponibles == 5)

    def test_lineas_repetidas_del_mismo_producto_se_reponen_bien(self):
        p = make_product(self.company, self.creador, "P", stock=10, tipo=self.tipo)
        fid = self._factura((p, 2), (p, 3))
        p.refresh_from_db(); self.assertEqual(p.unidades_disponibles, 5)
        self.cc.delete(f"/facturas/destroy/{fid}/")
        p.refresh_from_db(); self.assertEqual(p.unidades_disponibles, 10)

    def test_borrar_factura_con_producto_ya_nulo_no_falla(self):
        p = make_product(self.company, self.creador, "P", stock=10, tipo=self.tipo)
        fid = self._factura((p, 2))
        # Simula un producto borrado en el pasado (FacturaDetalle.producto = NULL)
        FacturaDetalle.objects.filter(factura_id=fid).update(producto=None)
        r = self.cc.delete(f"/facturas/destroy/{fid}/")
        self.assertIn(r.status_code, (200, 204))
        self.assertFalse(Factura.objects.filter(id=fid).exists())

    def test_worker_no_puede_borrar_factura(self):
        p = make_product(self.company, self.creador, "P", stock=10, tipo=self.tipo)
        fid = self._factura((p, 1))
        r = self.wc.delete(f"/facturas/destroy/{fid}/")
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Factura.objects.filter(id=fid).exists())


class SnapshotInmutableTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.p = make_product(self.company, self.creador, "P", stock=10, valor="1000")

    def test_facturadetalle_no_resnapshotea_al_reguardar(self):
        f = Factura.objects.create(subtotal=Decimal("2000"), total=Decimal("2000"),
                                   tienda=self.company, creado_por=self.creador)
        d = FacturaDetalle.objects.create(factura=f, producto=self.p, cantidad=2,
                                          subtotal=Decimal("2000"), tienda=self.company,
                                          creado_por=self.creador)
        self.assertEqual(d.valor_und, Decimal("1000"))
        self.assertEqual(d.nombre_producto, self.p.nombre)

        # El producto sube de precio y se re-guarda el detalle -> NO debe cambiar
        self.p.valor = Decimal("9999"); self.p.nombre = "Renombrado"; self.p.save()
        d.refresh_from_db()
        d.save()
        d.refresh_from_db()
        self.assertEqual(d.valor_und, Decimal("1000"))
        self.assertNotEqual(d.nombre_producto, "Renombrado")

    def test_descuento_de_linea_no_cambia_si_la_promo_se_desactiva_despues(self):
        from apps.base.tests.factories import make_company as _mc
        company, creador = _mc(nombre="tiendasnapshot", email="snap@test.com", nit="900555")
        tipo = make_tipo(company, creador)
        make_caja(company, creador)
        p = make_product(company, creador, "PromoP", stock=10, valor="1000", tipo=tipo)
        promo = make_descuento(p, creador, porcentaje="20")

        client = APIClient(); client.force_authenticate(creador)
        r = client.post("/facturas/create/",
                        {"detalles": [{"producto": p.id, "cantidad": 1}]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        d = FacturaDetalle.objects.get(factura_id=r.data["factura_id"])
        self.assertEqual(d.descuento_porcentaje, Decimal("20"))

        promo.activo = False
        promo.save()
        d.refresh_from_db()
        d.save()
        d.refresh_from_db()
        self.assertEqual(d.descuento_porcentaje, Decimal("20"))  # sin cambios


class ProtectCreadoPorTest(TestCase):
    def test_no_se_puede_borrar_usuario_que_creo_facturas(self):
        company, creador = make_company()
        worker = make_user("wrk", tipo=TipoUsuario.WORKER, company=company)
        p = make_product(company, creador, "P", stock=10)
        Factura.objects.create(subtotal=Decimal("1"), total=Decimal("1"), tienda=company, creado_por=worker)
        with self.assertRaises(ProtectedError):
            worker.delete()

    def test_no_se_puede_borrar_creador_de_empresa(self):
        company, creador = make_company()
        with self.assertRaises(ProtectedError):
            creador.delete()

    def test_borrar_empresa_sigue_funcionando(self):
        # tienda es CASCADE; borrar la empresa arrastra productos/facturas aunque
        # creado_por sea PROTECT (PROTECT solo aplica al borrar el usuario).
        company, creador = make_company()
        p = make_product(company, creador, "P", stock=10)
        Factura.objects.create(subtotal=Decimal("1"), total=Decimal("1"), tienda=company, creado_por=creador)
        cid = company.id
        company.delete()
        self.assertFalse(ProductModel.objects.filter(tienda_id=cid).exists())
        self.assertFalse(Factura.objects.filter(tienda_id=cid).exists())


class BorrarProductoConVentasTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
        self.c = APIClient(); self.c.force_authenticate(self.creador)

    def test_producto_con_ventas_no_se_borra(self):
        p = make_product(self.company, self.creador, "ConVentas", stock=10, tipo=self.tipo)
        f = Factura.objects.create(subtotal=p.valor, total=p.valor, tienda=self.company, creado_por=self.creador)
        FacturaDetalle.objects.create(factura=f, producto=p, cantidad=1, subtotal=p.valor,
                                      tienda=self.company, creado_por=self.creador)
        r = self.c.delete(f"/destroyproduct/{p.id}/")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertTrue(ProductModel.objects.filter(id=p.id).exists())

    def test_producto_sin_ventas_si_se_borra(self):
        p = make_product(self.company, self.creador, "SinVentas", stock=10, tipo=self.tipo)
        r = self.c.delete(f"/destroyproduct/{p.id}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(ProductModel.objects.filter(id=p.id).exists())
