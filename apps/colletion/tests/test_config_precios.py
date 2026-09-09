from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_company, make_user
from apps.colletion.api.serializers.serializer_config import CreateParametrosSerializer
from apps.colletion.models import Config_ProductModel


class CreateParametrosSerializerTest(TestCase):
    """`validate()` antes vivía dentro de `class Meta` y nunca se ejecutaba."""

    def test_costos_fijos_requerido(self):
        s = CreateParametrosSerializer(data={
            "margen_ganancia": "1.0", "promedio_productos_vendidos": 10,
        })
        self.assertFalse(s.is_valid())
        self.assertIn("costos_fijos", s.errors)

    def test_config_valida(self):
        s = CreateParametrosSerializer(data={
            "costos_fijos": "1000.00", "margen_ganancia": "1.0",
            "promedio_productos_vendidos": 10,
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_disponible_es_readonly(self):
        s = CreateParametrosSerializer(data={
            "costos_fijos": "1000.00", "promedio_productos_vendidos": 10,
            "disponible": False,
        })
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("disponible", s.validated_data)

    def test_costos_fijos_con_decimales_se_redondea(self):
        s = CreateParametrosSerializer(data={
            "costos_fijos": "50000.99", "margen_ganancia": "35.5",
            "promedio_productos_vendidos": 10,
        })
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["costos_fijos"], Decimal("50001"))
        # margen_ganancia conserva su decimal (es un %, no un importe).
        self.assertEqual(s.validated_data["margen_ganancia"], Decimal("35.5"))

    def test_rechaza_valores_sin_sentido(self):
        for over in (
            {"costos_fijos": "0"},
            {"costos_fijos": "-1000"},
            {"promedio_productos_vendidos": 0},
            {"promedio_productos_vendidos": -3},
            {"margen_ganancia": "1000"},
            {"margen_ganancia": "-1"},
        ):
            data = {
                "costos_fijos": "1000000", "margen_ganancia": "30.0",
                "promedio_productos_vendidos": 10,
            }
            data.update(over)
            s = CreateParametrosSerializer(data=data)
            self.assertFalse(s.is_valid(), f"{over} debería fallar")

    def test_margen_hasta_999_9_es_valido(self):
        s = CreateParametrosSerializer(data={
            "costos_fijos": "1000000", "margen_ganancia": "999.9",
            "promedio_productos_vendidos": 10,
        })
        self.assertTrue(s.is_valid(), s.errors)


class ConfigUpsertTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def _post(self, **over):
        data = {
            "costos_fijos": "1000000", "margen_ganancia": "20",
            "promedio_productos_vendidos": 50,
        }
        data.update(over)
        return self.client.post("/config/", data, format="json")

    def test_primero_crea_luego_actualiza(self):
        r = self._post()
        self.assertEqual(r.status_code, 201, r.data)

        r = self._post(costos_fijos="3000000", margen_ganancia="45",
                       promedio_productos_vendidos=120)
        self.assertEqual(r.status_code, 200, r.data)  # actualiza, no rechaza

        cfg = Config_ProductModel.objects.get(tienda=self.company)
        self.assertEqual(cfg.costos_fijos, Decimal("3000000"))
        self.assertEqual(cfg.margen_ganancia, Decimal("45.0"))
        self.assertEqual(cfg.promedio_productos_vendidos, 120)
        self.assertEqual(Config_ProductModel.objects.filter(tienda=self.company).count(), 1)

    def test_borrar_y_recrear(self):
        self.assertEqual(self._post().status_code, 201)
        r = self.client.delete("/config/destroy/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._post().status_code, 201)

    def test_admin_puede_ver_pero_no_editar(self):
        self._post()
        admin = make_user("cfadmin", tipo=TipoUsuario.ADMIN, company=self.company)
        ca = APIClient()
        ca.force_authenticate(user=admin)
        self.assertEqual(ca.get("/config/retrive/").status_code, 200)
        self.assertEqual(
            ca.post("/config/", {"costos_fijos": "1"}, format="json").status_code, 403
        )
        self.assertEqual(ca.delete("/config/destroy/").status_code, 403)


class PrecioSugeridoTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        Config_ProductModel.objects.create(
            tienda=self.company, creado_por=self.creador,
            costos_fijos=Decimal("100000"), margen_ganancia=Decimal("30.0"),
            promedio_productos_vendidos=7,  # 100000/7 = 14285.71...
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.creador)

    def test_precio_sugerido_sin_decimales(self):
        r = self.client.post("/config/calculo/", {"valor_mayor": 20000},
                             format="json")
        self.assertEqual(r.status_code, 200, r.data)
        precio = Decimal(str(r.data["Precio_sugerido_Unidad"]))
        cf = Decimal(str(r.data["ValorXmayor_CF"]))
        self.assertEqual(precio, precio.to_integral_value())
        self.assertEqual(cf, cf.to_integral_value())
