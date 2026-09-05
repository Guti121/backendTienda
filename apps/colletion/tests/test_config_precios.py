from django.test import TestCase

from apps.colletion.api.serializers.serializer_config import CreateParametrosSerializer


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
