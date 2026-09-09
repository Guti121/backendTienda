from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.tests.factories import make_company
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
