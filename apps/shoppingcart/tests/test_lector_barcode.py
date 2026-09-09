"""Lector de código de barras (apps/shoppingcart/api/codebar.py).

Tres endpoints, todos con permiso IsWorkerOrCreator (worker / creator / admin):
- POST /facturas/codigo_de_barras/       (imagen -> pyzbar.decode -> lookup)
- POST /facturas/codigo_de_barras_text/  (string 'codigoBarras' -> lookup)
- GET  /facturas/api/barcode/<product_pk>/  (RetrieveBarCode)

El lookup es SIEMPRE `Bar_codeModel.filter(code=..., tienda=company_owner(user))`,
así que un código de otra tienda "no existe" para ti.
"""
import io
from decimal import Decimal
from unittest import mock

import barcode
from barcode.writer import ImageWriter
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_company, make_tipo, make_user, png_file
from apps.colletion.models import Bar_codeModel, ProductModel
from apps.colletion.tasks import generar_codigo_barras_task

URL_IMG = "/facturas/codigo_de_barras/"
URL_TXT = "/facturas/codigo_de_barras_text/"


def _zbar_ok():
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode
        decode(Image.new("RGB", (4, 4)))
        return True
    except Exception:
        return False


def fake_decode(code):
    """Sustituto de pyzbar.decode: devuelve un 'símbolo' con .data = bytes."""
    return [mock.Mock(data=code.encode("utf-8"))]


class LectorBase(TestCase):
    def setUp(self):
        self.company, self.creador = make_company(
            nombre="tiendaA", email="a@test.com", nit="900001")
        self.tipo = make_tipo(self.company, self.creador)
        self.worker = make_user("worker_a", tipo=TipoUsuario.WORKER, company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(user=self.worker)

    def _producto(self, numero, stock=10, disponible=True, company=None, creador=None,
                  tipo=None, nombre="Prod"):
        company = company or self.company
        creador = creador or self.creador
        tipo = tipo or self.tipo
        p = ProductModel.objects.create(
            nombre=nombre, tipo_producto=tipo, detalles="x",
            valor_mayor=Decimal("500"), valor=Decimal("1000"),
            unidades_disponibles=stock, tienda=company, creado_por=creador,
            numero_producto=numero,
        )
        if not disponible:
            ProductModel.objects.filter(pk=p.pk).update(disponible=False)
            p.refresh_from_db()
        generar_codigo_barras_task.delay(p.id)
        return p, Bar_codeModel.objects.get(product=p)


class LectorTextoTest(LectorBase):
    def test_codigo_valido_devuelve_el_producto(self):
        p, cb = self._producto("10001")
        r = self.client.post(URL_TXT, {"codigoBarras": cb.code, "cantidad": 1}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["id"], p.id)
        self.assertEqual(r.data["nombre"], p.nombre)
        self.assertEqual(r.data["unidades_disponibles"], 10)

    def test_creator_tambien_puede(self):
        _, cb = self._producto("10002")
        cc = APIClient()
        cc.force_authenticate(user=self.creador)
        r = cc.post(URL_TXT, {"codigoBarras": cb.code}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

    def test_rol_cliente_403(self):
        _, cb = self._producto("10003")
        cli = make_user("cli_a", tipo=TipoUsuario.CLIENTE, company=self.company)
        cc = APIClient()
        cc.force_authenticate(user=cli)
        self.assertEqual(
            cc.post(URL_TXT, {"codigoBarras": cb.code}, format="json").status_code, 403
        )

    def test_sin_codigo_400(self):
        r = self.client.post(URL_TXT, {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_codigo_inexistente_400(self):
        r = self.client.post(URL_TXT, {"codigoBarras": "7700123999998"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("mensaje", r.data)

    def test_codigo_de_otra_tienda_no_se_ve(self):
        otra, cr = make_company(nombre="tiendaB", email="b@test.com", nit="900002")
        _, cbB = self._producto("10004", company=otra, creador=cr,
                                tipo=make_tipo(otra, cr))
        r = self.client.post(URL_TXT, {"codigoBarras": cbB.code}, format="json")
        self.assertEqual(r.status_code, 400)  # para la tienda A ese código no existe

    def test_stock_insuficiente_400(self):
        _, cb = self._producto("10005", stock=3)
        r = self.client.post(URL_TXT, {"codigoBarras": cb.code, "cantidad": 5}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.data)

    def test_producto_no_disponible_400(self):
        _, cb = self._producto("10006", disponible=False)
        r = self.client.post(URL_TXT, {"codigoBarras": cb.code, "cantidad": 1}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_cantidad_igual_al_stock_ok(self):
        _, cb = self._producto("10007", stock=4)
        r = self.client.post(URL_TXT, {"codigoBarras": cb.code, "cantidad": 4}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

    def test_cantidad_no_numerica_no_revienta_feo(self):
        # QUIRK: el except del endpoint devuelve Response sin status -> 200 aunque
        # int("abc") falló. Documenta el comportamiento actual (debería ser 400).
        _, cb = self._producto("10008")
        r = self.client.post(URL_TXT, {"codigoBarras": cb.code, "cantidad": "abc"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("error", r.data)


class LectorImagenTest(LectorBase):
    def _img(self, name="cb.png"):
        return SimpleUploadedFile(name, png_file().read(), content_type="image/png")

    def test_sin_imagen_400(self):
        r = self.client.post(URL_IMG, {"cantidad": 1}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.data)

    def test_decodifica_y_devuelve_producto(self):
        p, cb = self._producto("20001")
        with mock.patch("apps.shoppingcart.api.codebar.decode",
                        return_value=fake_decode(cb.code)):
            r = self.client.post(URL_IMG, {"imagen": self._img(), "cantidad": 1},
                                 format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["id"], p.id)

    def test_imagen_sin_codigo_400(self):
        with mock.patch("apps.shoppingcart.api.codebar.decode", return_value=[]):
            r = self.client.post(URL_IMG, {"imagen": self._img()}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("mensaje", r.data)

    def test_codigo_no_encontrado_devuelve_204(self):
        # QUIRK: cuando el código decodifica pero no está en la BD, este endpoint
        # responde 204 (No Content) con cuerpo — el de texto responde 400. Muchos
        # clientes descartan el cuerpo de un 204.
        with mock.patch("apps.shoppingcart.api.codebar.decode",
                        return_value=fake_decode("7700123999998")):
            r = self.client.post(URL_IMG, {"imagen": self._img()}, format="multipart")
        self.assertEqual(r.status_code, 204)

    def test_stock_insuficiente_400(self):
        _, cb = self._producto("20002", stock=1)
        with mock.patch("apps.shoppingcart.api.codebar.decode",
                        return_value=fake_decode(cb.code)):
            r = self.client.post(URL_IMG, {"imagen": self._img(), "cantidad": 9},
                                 format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_rol_cliente_403(self):
        cli = make_user("cli_img", tipo=TipoUsuario.CLIENTE, company=self.company)
        cc = APIClient()
        cc.force_authenticate(user=cli)
        r = cc.post(URL_IMG, {"imagen": self._img()}, format="multipart")
        self.assertEqual(r.status_code, 403)

    def test_imagen_corrupta_devuelve_500(self):
        # QUIRK: cualquier excepción (aquí PIL no puede abrir la imagen) se
        # traduce a 500 con str(e) en el cuerpo (fuga de detalle interno).
        bad = SimpleUploadedFile("x.png", b"no soy una imagen", content_type="image/png")
        r = self.client.post(URL_IMG, {"imagen": bad}, format="multipart")
        self.assertEqual(r.status_code, 500)


class LectorImagenRealTest(LectorBase):
    """Ensayo de verdad del lector: imagen EAN-13 real -> pyzbar -> producto.
    Se salta si el binario nativo de zbar no está disponible (CI sin libzbar0)."""

    def setUp(self):
        if not _zbar_ok():
            self.skipTest("zbar (pyzbar) no disponible en este entorno")
        super().setUp()

    def _imagen_ean13(self, code12):
        ean = barcode.get("ean13", code12, writer=ImageWriter())
        buf = io.BytesIO()
        ean.write(buf, {"format": "PNG"})
        buf.seek(0)
        return SimpleUploadedFile("real.png", buf.read(), content_type="image/png"), \
            ean.get_fullcode()

    def test_lee_imagen_ean13_generada(self):
        p, cb = self._producto("24680")  # code12 = 7700123 + 24680
        img, fullcode = self._imagen_ean13("770012324680")
        self.assertEqual(fullcode, cb.code)  # lo que guarda crear_codigo_barras

        r = self.client.post(URL_IMG, {"imagen": img, "cantidad": 1}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["id"], p.id)
        self.assertEqual(r.data["nombre"], p.nombre)


class RetrieveBarCodeTest(LectorBase):
    def test_devuelve_nombre_y_barcode(self):
        p, cb = self._producto("30001", nombre="Camisa")
        r = self.client.get(f"/facturas/api/barcode/{p.id}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["nombre"], p.nombre)
        self.assertIn("barcode", r.data)

    def test_producto_de_otra_tienda_404(self):
        otra, cr = make_company(nombre="tiendaB", email="b@test.com", nit="900002")
        pB, _ = self._producto("30002", company=otra, creador=cr, tipo=make_tipo(otra, cr))
        self.assertEqual(
            self.client.get(f"/facturas/api/barcode/{pB.id}/").status_code, 404
        )

    def test_no_autenticado_401(self):
        p, _ = self._producto("30003")
        anon = APIClient()
        self.assertEqual(anon.get(f"/facturas/api/barcode/{p.id}/").status_code, 401)
