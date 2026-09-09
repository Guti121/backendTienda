"""Personalización del catálogo público por tienda: catalog_font /
catalog_tagline / catalog_announcement / catalog_banner en Company.

Se editan por el mismo endpoint que los datos de la tienda
(PATCH /store/updateCompany/, solo creator) y se leen tanto en
GET /store/retrieveCompany/ (dueño) como en el endpoint público
GET /catalogo/company/<name>.
"""

from django.core.files.storage import default_storage
from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_company, make_user, png_file
from apps.myStore.models import Company


class CatalogAppearanceUpdateTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company(nombre="tiendauno")
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def _patch(self, data, fmt="multipart"):
        return self.client.patch("/store/updateCompany/", data, format=fmt)

    def test_creator_actualiza_textos_y_fuente(self):
        r = self._patch({
            "catalog_font": "geometric",
            "catalog_tagline": "Envíos a todo el país",
            "catalog_announcement": "2x1 esta semana",
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.company.refresh_from_db()
        self.assertEqual(self.company.catalog_font, "geometric")
        self.assertEqual(self.company.catalog_tagline, "Envíos a todo el país")
        self.assertEqual(self.company.catalog_announcement, "2x1 esta semana")

    def test_fuente_fuera_de_choices_es_400(self):
        r = self._patch({"catalog_font": "comic-sans"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("catalog_font", r.data)

    def test_tagline_demasiado_larga_es_400(self):
        r = self._patch({"catalog_tagline": "x" * 121})
        self.assertEqual(r.status_code, 400)
        self.assertIn("catalog_tagline", r.data)

    def test_subir_banner_y_reemplazarlo_borra_el_anterior(self):
        r = self._patch({"catalog_banner": png_file("b1.png")})
        self.assertEqual(r.status_code, 200, r.data)
        self.company.refresh_from_db()
        primero = self.company.catalog_banner.name
        self.assertTrue(primero)
        self.assertTrue(default_storage.exists(primero))

        r = self._patch({"catalog_banner": png_file("b2.png")})
        self.assertEqual(r.status_code, 200, r.data)
        self.company.refresh_from_db()
        segundo = self.company.catalog_banner.name
        self.assertNotEqual(primero, segundo)
        self.assertFalse(default_storage.exists(primero))
        self.assertTrue(default_storage.exists(segundo))

    def test_no_creator_no_puede(self):
        worker = make_user("empleado", tipo=TipoUsuario.WORKER, company=self.company)
        c = APIClient()
        c.force_authenticate(user=worker)
        r = c.patch("/store/updateCompany/", {"catalog_tagline": "hola"},
                    format="multipart")
        self.assertEqual(r.status_code, 403)

    def test_creator_actualiza_paleta_y_colores(self):
        r = self._patch({
            "catalog_palette": "menta",
            "catalog_color_accent": "#0d9488",
            "catalog_color_bg": "#f0fdfa",
            "catalog_color_text": "#134e4a",
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.company.refresh_from_db()
        self.assertEqual(self.company.catalog_palette, "menta")
        self.assertEqual(self.company.catalog_color_accent, "#0d9488")
        self.assertEqual(self.company.catalog_color_bg, "#f0fdfa")
        self.assertEqual(self.company.catalog_color_text, "#134e4a")

    def test_hex_invalido_es_400(self):
        for value in ("rojo", "#12", "4f46e5", "#gggggg"):
            r = self._patch({"catalog_color_accent": value})
            self.assertEqual(r.status_code, 400, f"{value!r} debería fallar")
            self.assertIn("catalog_color_accent", r.data)

    def test_paleta_fuera_de_choices_es_400(self):
        r = self._patch({"catalog_palette": "neon"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("catalog_palette", r.data)

    def test_color_vacio_se_acepta(self):
        # "" = sin override, vuelve a la paleta.
        r = self._patch({"catalog_color_accent": ""})
        self.assertEqual(r.status_code, 200, r.data)

    def test_creator_actualiza_colores_finos_v3(self):
        r = self._patch({
            "catalog_color_surface": "#ffffff",
            "catalog_color_muted": "#64748b",
            "catalog_color_heading": "#0f172a",
            "catalog_color_border": "#e2e8f0",
            "catalog_color_accent_soft": "#eef2ff",
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.company.refresh_from_db()
        self.assertEqual(self.company.catalog_color_surface, "#ffffff")
        self.assertEqual(self.company.catalog_color_muted, "#64748b")
        self.assertEqual(self.company.catalog_color_heading, "#0f172a")
        self.assertEqual(self.company.catalog_color_border, "#e2e8f0")
        self.assertEqual(self.company.catalog_color_accent_soft, "#eef2ff")

    def test_hex_invalido_en_color_fino_es_400(self):
        r = self._patch({"catalog_color_surface": "blanco"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("catalog_color_surface", r.data)


class CatalogAppearanceReadTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company(nombre="tiendbella")

    def test_retrieve_del_dueno_incluye_los_campos(self):
        c = APIClient()
        c.force_authenticate(user=self.creador)
        r = c.get("/store/retrieveCompany/")
        self.assertEqual(r.status_code, 200, r.data)
        for f in ("catalog_font", "catalog_tagline", "catalog_announcement",
                  "catalog_banner", "catalog_palette", "catalog_color_accent",
                  "catalog_color_bg", "catalog_color_text",
                  "catalog_color_surface", "catalog_color_muted",
                  "catalog_color_heading", "catalog_color_border",
                  "catalog_color_accent_soft"):
            self.assertIn(f, r.data)

    def test_endpoint_publico_defaults(self):
        r = APIClient().get(f"/catalogo/company/{self.company.name}")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["catalog_font"], "")
        self.assertEqual(r.data["catalog_tagline"], "")
        self.assertEqual(r.data["catalog_announcement"], "")
        self.assertIsNone(r.data["catalog_banner"])
        self.assertEqual(r.data["catalog_palette"], "")
        self.assertEqual(r.data["catalog_color_accent"], "")
        self.assertEqual(r.data["catalog_color_bg"], "")
        self.assertEqual(r.data["catalog_color_text"], "")
        for f in ("catalog_color_surface", "catalog_color_muted",
                  "catalog_color_heading", "catalog_color_border",
                  "catalog_color_accent_soft"):
            self.assertEqual(r.data[f], "")

    def test_endpoint_publico_devuelve_banner_absoluto(self):
        c = APIClient()
        c.force_authenticate(user=self.creador)
        c.patch("/store/updateCompany/", {
            "catalog_font": "serif",
            "catalog_banner": png_file("hero.png"),
        }, format="multipart")

        r = APIClient().get(f"/catalogo/company/{self.company.name}")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["catalog_font"], "serif")
        self.assertTrue(r.data["catalog_banner"].startswith("http"))
