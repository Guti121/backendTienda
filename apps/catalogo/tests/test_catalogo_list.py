"""Búsqueda por nombre (?q=) en el listado público del catálogo.

`GET /catalogo/list/<tienda>` no requiere auth. Antes solo filtraba por
categoría (?tipo=) y orden (?orden/?fecha); aquí se cubre el nuevo ?q=.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.tests.factories import make_categoria, make_company, make_tipo, make_product
from apps.colletion.models import ProductModel


def _publicar(*productos):
    """`make_product` deja publicar=False; el catálogo solo muestra
    publicar=True + disponible=True. Se hace con .update() para no re-disparar
    save() (que capitaliza el nombre y encola la tarea de barcode)."""
    ids = [p.pk for p in productos]
    ProductModel.objects.filter(pk__in=ids).update(publicar=True, disponible=True)


class CatalogoBusquedaNombreTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company, self.creador = make_company(nombre="tiendauno")
        self.tipo_ropa = make_tipo(self.company, self.creador, nombre="Ropa")
        self.tipo_calzado = make_tipo(self.company, self.creador, nombre="Calzado")

        self.camiseta = make_product(
            self.company, self.creador, nombre="Camiseta Azul", tipo=self.tipo_ropa,
        )
        self.camisa = make_product(
            self.company, self.creador, nombre="Camisa Blanca", tipo=self.tipo_ropa,
        )
        self.zapato = make_product(
            self.company, self.creador, nombre="Zapato Negro", tipo=self.tipo_calzado,
        )
        _publicar(self.camiseta, self.camisa, self.zapato)

        self.url = f"/catalogo/list/{self.company.name}"

    def _nombres(self, resp):
        return sorted(item["nombre"] for item in resp.data["results"])

    def test_sin_q_devuelve_todo(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 3)

    def test_q_substring_filtra_por_nombre(self):
        resp = self.client.get(self.url, {"q": "cami"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 2)
        self.assertEqual(self._nombres(resp), ["Camisa Blanca", "Camiseta Azul"])

    def test_q_es_case_insensitive(self):
        resp = self.client.get(self.url, {"q": "CAMISETA"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._nombres(resp), ["Camiseta Azul"])

    def test_q_sin_coincidencias_devuelve_lista_vacia(self):
        resp = self.client.get(self.url, {"q": "zzzzzz"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)
        self.assertEqual(resp.data["results"], [])

    def test_q_en_blanco_se_ignora(self):
        resp = self.client.get(self.url, {"q": "   "})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 3)

    def test_q_respeta_publicar_y_disponible(self):
        oculto = make_product(
            self.company, self.creador, nombre="Camiseta Oculta", tipo=self.tipo_ropa,
        )  # queda publicar=False
        resp = self.client.get(self.url, {"q": "camiseta"})
        self.assertEqual(self._nombres(resp), ["Camiseta Azul"])
        self.assertNotIn("Camiseta Oculta", self._nombres(resp))
        del oculto

    def test_q_combina_con_tipo(self):
        resp = self.client.get(
            self.url, {"q": "a", "tipo": self.tipo_calzado.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._nombres(resp), ["Zapato Negro"])

    def test_q_respeta_aislamiento_por_tienda(self):
        otra, otro_creador = make_company(nombre="tiendados", nit="900999",
                                          email="dos@test.com")
        otro_tipo = make_tipo(otra, otro_creador, nombre="Ropa")
        ajena = make_product(otra, otro_creador, nombre="Camiseta Ajena", tipo=otro_tipo)
        _publicar(ajena)

        resp = self.client.get(self.url, {"q": "camiseta"})
        self.assertEqual(self._nombres(resp), ["Camiseta Azul"])

    def test_respuesta_sigue_paginada(self):
        resp = self.client.get(self.url, {"q": "cami"})
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, resp.data)


class CatalogoPaginacionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company, self.creador = make_company(nombre="tiendabulk")
        self.tipo = make_tipo(self.company, self.creador, nombre="General")
        prods = [
            make_product(
                self.company, self.creador, nombre=f"Prod {i:02}", tipo=self.tipo,
            )
            for i in range(35)
        ]
        _publicar(*prods)
        self.url = f"/catalogo/list/{self.company.name}"

    def test_pagina_trae_30_por_defecto(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 35)
        self.assertEqual(len(resp.data["results"]), 30)
        self.assertIsNotNone(resp.data["next"])

    def test_page_size_configurable_con_tope(self):
        self.assertEqual(
            len(self.client.get(self.url, {"page_size": 10}).data["results"]), 10
        )
        # max_page_size = 60 -> pedir 100 devuelve los 35, no falla
        self.assertEqual(
            len(self.client.get(self.url, {"page_size": 100}).data["results"]), 35
        )


class CatalogoCategoriaTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company, self.creador = make_company(nombre="tiendacat")
        self.cat_ropa = make_categoria(self.company, self.creador, "Ropa")
        self.tipo_camisetas = make_tipo(
            self.company, self.creador, nombre="Camisetas", categoria=self.cat_ropa,
        )
        self.tipo_calzado = make_tipo(self.company, self.creador, nombre="Calzado")  # sin categoría

        self.camiseta = make_product(
            self.company, self.creador, nombre="Camiseta Azul", tipo=self.tipo_camisetas,
        )
        self.zapato = make_product(
            self.company, self.creador, nombre="Zapato Negro", tipo=self.tipo_calzado,
        )
        _publicar(self.camiseta, self.zapato)

    def test_tipo_producto_list_incluye_categoria(self):
        r = self.client.get(f"/catalogo/tipo-producto/{self.company.name}")
        self.assertEqual(r.status_code, 200, r.data)
        by_name = {t["tipo_producto"]: t for t in r.data}
        self.assertEqual(by_name["Camisetas"]["categoria_id"], self.cat_ropa.id)
        self.assertEqual(by_name["Camisetas"]["categoria_nombre"], "Ropa")
        self.assertIsNone(by_name["Calzado"]["categoria_id"])
        self.assertIsNone(by_name["Calzado"]["categoria_nombre"])

    def test_filtro_por_categoria(self):
        url = f"/catalogo/list/{self.company.name}"
        r = self.client.get(url, {"categoria": self.cat_ropa.id})
        self.assertEqual(r.status_code, 200, r.data)
        nombres = [p["nombre"] for p in r.data["results"]]
        self.assertEqual(nombres, ["Camiseta Azul"])

    def test_categoria_no_numerica_400(self):
        url = f"/catalogo/list/{self.company.name}"
        r = self.client.get(url, {"categoria": "abc"})
        self.assertEqual(r.status_code, 400, r.data)

    def test_categoria_aparece_en_list_y_detail(self):
        url = f"/catalogo/list/{self.company.name}"
        r = self.client.get(url, {"q": "Camiseta"})
        self.assertEqual(r.data["results"][0]["categoria"], "Ropa")

        r = self.client.get(f"/catalogo/product/{self.company.name}/{self.camiseta.id}")
        self.assertEqual(r.data["categoria"], "Ropa")
