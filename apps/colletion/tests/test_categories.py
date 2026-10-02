from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.tests.factories import make_categoria, make_company, make_tipo
from apps.colletion.models import CategoryModel, TypeProductModel


class CategoryCreateTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_crear_categoria_ok(self):
        r = self.client.post("/createcategory/", {"nombre": "Ropa de hombre"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(CategoryModel.objects.get().nombre, "Ropa de hombre")

    def test_nombre_vacio_400(self):
        r = self.client.post("/createcategory/", {"nombre": ""}, format="json")
        self.assertEqual(r.status_code, 400, r.data)

    def test_duplicado_en_la_misma_tienda_400(self):
        make_categoria(self.company, self.creador, "Cocina")
        r = self.client.post("/createcategory/", {"nombre": "Cocina"}, format="json")
        self.assertEqual(r.status_code, 400, r.data)


class CategoryListFilterTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_listado_ordenado_por_nombre(self):
        make_categoria(self.company, self.creador, "Cuarto")
        make_categoria(self.company, self.creador, "Cocina")
        r = self.client.get("/listCategory/")
        self.assertEqual(r.status_code, 200, r.data)
        nombres = [c["nombre"] for c in r.data["results"]]
        self.assertEqual(nombres, ["Cocina", "Cuarto"])

    def test_filtro_por_q(self):
        make_categoria(self.company, self.creador, "Ropa de hombre")
        make_categoria(self.company, self.creador, "Ropa de mujer")
        make_categoria(self.company, self.creador, "Calzado")
        r = self.client.get("/categoryFilter/", {"q": "ropa"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["count"], 2)


class CategoryUpdateDestroyTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.categoria = make_categoria(self.company, self.creador, "Cocina")
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_renombrar(self):
        r = self.client.patch(
            f"/categoryUpdate/{self.categoria.id}/", {"nombre": "Hogar"}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.nombre, "Hogar")

    def test_borrar_no_borra_los_tipos_los_deja_sin_categoria(self):
        tipo = make_tipo(self.company, self.creador, "Ollas", categoria=self.categoria)
        r = self.client.delete(f"/destroycategory/{self.categoria.id}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(CategoryModel.objects.filter(id=self.categoria.id).exists())
        tipo.refresh_from_db()
        self.assertIsNotNone(TypeProductModel.objects.get(id=tipo.id))
        self.assertIsNone(tipo.categoria)


class TypeProductoConCategoriaTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.categoria = make_categoria(self.company, self.creador, "Ropa de hombre")
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_crear_tipo_con_categoria(self):
        r = self.client.post(
            "/createtype/",
            {"tipo_producto": "Camisetas", "categoria": self.categoria.id},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        tipo = TypeProductModel.objects.get()
        self.assertEqual(tipo.categoria_id, self.categoria.id)
        self.assertEqual(r.data["categoria_nombre"], "Ropa de hombre")

    def test_crear_tipo_sin_categoria_sigue_funcionando(self):
        r = self.client.post("/createtype/", {"tipo_producto": "Camisetas"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(TypeProductModel.objects.get().categoria)
        self.assertIsNone(r.data["categoria_nombre"])

    def test_categoria_de_otra_tienda_rechazada(self):
        otra_company, otro_creador = make_company(nombre="otratienda", email="otra@test.com", nit="900999")
        otra_categoria = make_categoria(otra_company, otro_creador, "Ajena")
        r = self.client.post(
            "/createtype/",
            {"tipo_producto": "Camisetas", "categoria": otra_categoria.id},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)

    def test_categoria_nombre_aparece_en_listType(self):
        make_tipo(self.company, self.creador, "Camisetas", categoria=self.categoria)
        r = self.client.get("/listType/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["results"][0]["categoria_nombre"], "Ropa de hombre")

    def test_filtro_de_tipos_por_categoria(self):
        otra_categoria = make_categoria(self.company, self.creador, "Ropa de mujer")
        make_tipo(self.company, self.creador, "Camisetas", categoria=self.categoria)
        make_tipo(self.company, self.creador, "Pantalones", categoria=self.categoria)
        make_tipo(self.company, self.creador, "Blusas", categoria=otra_categoria)
        make_tipo(self.company, self.creador, "Suelto")  # sin categoría

        r = self.client.get("/typeProductFilter/", {"categoria": self.categoria.id})
        self.assertEqual(r.status_code, 200, r.data)
        nombres = {t["tipo_producto"] for t in r.data["results"]}
        self.assertEqual(nombres, {"Camisetas", "Pantalones"})

        r = self.client.get("/listType/", {"categoria": self.categoria.id})
        self.assertEqual(r.status_code, 200, r.data)
        nombres = {t["tipo_producto"] for t in r.data["results"]}
        self.assertEqual(nombres, {"Camisetas", "Pantalones"})

        r = self.client.get("/typeProductFilter/", {"categoria": "abc"})
        self.assertEqual(r.status_code, 200, r.data)  # paginado: queryset.none() -> resultados vacíos
        self.assertEqual(r.data["results"], [])
