from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.base.tests.factories import make_categoria, make_company, make_descuento, make_product, make_tipo, png_file
from apps.colletion.models import ProductImage, ProductModel


class ProductCreateValidationTest(TestCase):
    """La validación del alta vive SOLO en ProductModelSerializer.validate()."""

    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def _post(self, **over):
        payload = {
            "nombre": "Prod X", "tipo_producto": self.tipo.id, "detalles": "d",
            "valor": "1000", "valor_mayor": "500", "unidades_disponibles": "5",
        }
        payload.update(over)
        return self.client.post("/create/", payload, format="json")

    def test_alta_valida(self):
        r = self._post(nombre="Buen Producto")
        self.assertEqual(r.status_code, 201, r.data)
        p = ProductModel.objects.get(nombre="Buen Producto")
        self.assertTrue(p.numero_producto)  # generado por el modelo
        self.assertTrue(p.disponible)

    def test_valor_menor_que_mayor(self):
        r = self._post(valor="400", valor_mayor="500")
        self.assertEqual(r.status_code, 400)
        self.assertIn("valor", r.data)

    def test_unidades_cero(self):
        r = self._post(unidades_disponibles="0")
        self.assertEqual(r.status_code, 400)
        self.assertIn("unidades_disponibles", r.data)

    def test_nombre_duplicado_case_insensitive(self):
        self.assertEqual(self._post(nombre="Repetido").status_code, 201)
        r = self._post(nombre="repetido")
        self.assertEqual(r.status_code, 400)
        self.assertIn("nombre", r.data)

    def test_cliente_no_puede_fijar_numero_producto_ni_disponible(self):
        r = self._post(nombre="Sin Trampa", numero_producto="00000", disponible=False)
        self.assertEqual(r.status_code, 201, r.data)
        p = ProductModel.objects.get(nombre="Sin Trampa")
        self.assertNotEqual(p.numero_producto, "00000")
        self.assertTrue(p.disponible)

    def test_precio_con_decimales_se_redondea_al_alta(self):
        # El front puede mandar decimales; se redondea al peso (HALF_UP).
        r = self._post(nombre="Con Centavos", valor="1234.56", valor_mayor="800.4")
        self.assertEqual(r.status_code, 201, r.data)
        p = ProductModel.objects.get(nombre="Con Centavos")
        self.assertEqual(p.valor, Decimal("1235"))
        self.assertEqual(p.valor_mayor, Decimal("800"))

    def test_editar_precio_con_decimales_se_redondea(self):
        self.assertEqual(self._post(nombre="Editable").status_code, 201)
        p = ProductModel.objects.get(nombre="Editable")
        r = self.client.patch(
            f"/updateProduct/{p.id}/", {"valor": "999.4"}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        p.refresh_from_db()
        self.assertEqual(p.valor, Decimal("999"))


class ProductListPerfTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        # Con categoría asignada: si `_productos_de()` no hace select_related
        # de 'tipo_producto__categoria', este test de N+1 lo detecta.
        self.categoria = make_categoria(self.company, self.creador, "Electronica")
        self.tipo = make_tipo(self.company, self.creador, categoria=self.categoria)
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def _crear(self, n):
        for i in range(n):
            p = ProductModel.objects.create(
                nombre=f"P{i}", tipo_producto=self.tipo, detalles="x",
                valor_mayor=Decimal("500"), valor=Decimal(1000 + i),
                unidades_disponibles=50, tienda=self.company, creado_por=self.creador,
            )
            ProductImage.objects.create(
                producto=p, imagen=png_file(f"p{i}.png"),
                tienda=self.company, creado_por=self.creador,
            )

    def test_listado_sin_n_mas_1(self):
        self._crear(2)
        with CaptureQueriesContext(connection) as q2:
            self.assertEqual(self.client.get("/list/").status_code, 200)

        ProductModel.objects.all().delete()
        self._crear(6)
        with CaptureQueriesContext(connection) as q6:
            self.assertEqual(self.client.get("/list/").status_code, 200)

        self.assertEqual(
            len(q2.captured_queries), len(q6.captured_queries),
            f"N+1: 2 prod -> {len(q2.captured_queries)} queries, 6 prod -> {len(q6.captured_queries)}",
        )

    def test_categoria_aparece_en_list_y_detail(self):
        self._crear(1)
        p = ProductModel.objects.get()

        r = self.client.get("/product/")
        self.assertEqual(r.data["results"][0]["categoria"], "Electronica", r.data)

        r = self.client.get(f"/productDetail/{p.id}/")
        self.assertEqual(r.data["categoria"], "Electronica", r.data)

    def test_busqueda_por_valor_numerico_y_texto(self):
        self._crear(3)  # valores 1000, 1001, 1002
        r = self.client.get("/product/", {"q": "1001"})
        self.assertEqual(r.status_code, 200, r.data)
        nombres = [p["nombre"] for p in r.data.get("results", r.data)]
        self.assertIn("P1", nombres)

        r = self.client.get("/product/", {"q": "texto-basura"})
        self.assertIn(r.status_code, (200, 404))  # nunca 500


class ListadoAdminIncluyePublicarTest(TestCase):
    """El listado admin (`/product/`) trae `publicar`: en la app se ve sin
    tener que entrar al detalle de cada producto."""

    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_trae_publicar(self):
        privado = make_product(self.company, self.creador, "Privado", tipo=self.tipo)
        publico = make_product(self.company, self.creador, "Publico", tipo=self.tipo)
        ProductModel.objects.filter(pk=publico.pk).update(publicar=True)

        r = self.client.get("/product/")
        self.assertEqual(r.status_code, 200, r.data)
        por_nombre = {p["nombre"]: p["publicar"] for p in r.data["results"]}
        self.assertFalse(por_nombre["Privado"])
        self.assertTrue(por_nombre["Publico"])


class ProductoConDescuentoSerializerTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_sin_promo_descuento_cero_y_valor_sin_cambios(self):
        make_product(self.company, self.creador, "Sin Promo", valor="1000", tipo=self.tipo)
        r = self.client.get("/product/")
        item = r.data["results"][0] if "results" in r.data else r.data[0]
        self.assertEqual(Decimal(str(item["descuento_porcentaje"])), Decimal("0"))
        self.assertEqual(Decimal(str(item["valor_con_descuento"])), Decimal("1000"))

    def test_con_promo_vigente_descuenta_el_precio(self):
        p = make_product(self.company, self.creador, "Con Promo", valor="1000", tipo=self.tipo)
        make_descuento(p, self.creador, porcentaje="20")
        r = self.client.get(f"/productDetail/{p.id}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data["descuento_porcentaje"])), Decimal("20"))
        self.assertEqual(Decimal(str(r.data["valor_con_descuento"])), Decimal("800"))
