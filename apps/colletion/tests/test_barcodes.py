from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.base.tests.factories import make_company, make_tipo
from apps.colletion.models import Bar_codeModel, ProductModel
from apps.colletion.tasks import generar_codigo_barras_task


class BarcodeTaskTest(TestCase):
    _seq = 54320

    def setUp(self):
        self.company, self.creador = make_company()
        self.tipo = make_tipo(self.company, self.creador)

    def _producto_sin_codigo(self, nombre="SinCB"):
        # Bypass del save() del modelo para no disparar la tarea todavía.
        BarcodeTaskTest._seq += 1
        p = ProductModel(
            nombre=nombre, tipo_producto=self.tipo, detalles="x",
            valor_mayor=Decimal("500"), valor=Decimal("1000"),
            unidades_disponibles=10, numero_producto=str(BarcodeTaskTest._seq),
            tienda=self.company, creado_por=self.creador,
        )
        super(ProductModel, p).save()
        return p

    def test_eager_activo_en_tests(self):
        self.assertTrue(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False))

    def test_task_genera_codigo(self):
        p = self._producto_sin_codigo()
        generar_codigo_barras_task.delay(p.id)
        cb = Bar_codeModel.objects.get(product=p)
        self.assertEqual(len(cb.code), 13)

    def test_task_idempotente(self):
        p = self._producto_sin_codigo()
        generar_codigo_barras_task.delay(p.id)
        generar_codigo_barras_task.delay(p.id)
        self.assertEqual(Bar_codeModel.objects.filter(product=p).count(), 1)

    def test_task_producto_inexistente_no_falla(self):
        generar_codigo_barras_task.delay(999999)

    def test_crear_producto_encola_via_on_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            p = ProductModel.objects.create(
                nombre="ConCB", tipo_producto=self.tipo, detalles="x",
                valor_mayor=Decimal("500"), valor=Decimal("1000"),
                unidades_disponibles=10, tienda=self.company, creado_por=self.creador,
            )
        self.assertTrue(Bar_codeModel.objects.filter(product=p).exists())

    def test_backfill_command(self):
        p1 = self._producto_sin_codigo("BF1")
        p2 = self._producto_sin_codigo("BF2")
        call_command("backfill_barcodes", "--sync")
        self.assertTrue(Bar_codeModel.objects.filter(product=p1).exists())
        self.assertTrue(Bar_codeModel.objects.filter(product=p2).exists())
