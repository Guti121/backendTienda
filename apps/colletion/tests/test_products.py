from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.base.tests.factories import make_company, make_tipo, png_file
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


class ProductListPerfTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)
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

    def test_busqueda_por_valor_numerico_y_texto(self):
        self._crear(3)  # valores 1000, 1001, 1002
        r = self.client.get("/product/", {"q": "1001"})
        self.assertEqual(r.status_code, 200, r.data)
        nombres = [p["nombre"] for p in r.data.get("results", r.data)]
        self.assertIn("P1", nombres)

        r = self.client.get("/product/", {"q": "texto-basura"})
        self.assertIn(r.status_code, (200, 404))  # nunca 500
