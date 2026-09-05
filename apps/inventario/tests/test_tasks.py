from django.test import TestCase
from django.utils import timezone

from apps.inventario.tasks import _hoy_local


class HoyLocalTest(TestCase):
    def test_es_dinamico(self):
        # _hoy_local() debe recalcularse en cada llamada, no ser una constante
        # de módulo (que quedaría congelada al arrancar el worker Celery).
        self.assertEqual(_hoy_local(), timezone.localtime(timezone.now()).date())

    def test_no_hay_now_local_de_modulo(self):
        import apps.inventario.tasks as t
        self.assertFalse(hasattr(t, "now_local"))
