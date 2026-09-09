from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.base.tests.factories import make_company, make_tipo
from apps.colletion.models import Bar_codeModel, ProductModel
from apps.colletion.tasks import generar_codigo_barras_task


def ean13_check_digit(payload12):
    """Dígito de control EAN-13 de un payload de 12 dígitos."""
    nums = [int(c) for c in payload12]
    impares = sum(nums[0::2])   # posiciones 1,3,5,... (índice par)
    pares = sum(nums[1::2])     # posiciones 2,4,6,... (índice impar)
    return (10 - (impares + 3 * pares) % 10) % 10


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


class NumeroProductoTest(TestCase):
    """Tope de numeración del código de barras.

    `numero_producto` = str(random.randint(10000, 99999)) → 5 dígitos, 90.000
    valores, único POR TIENDA (`generate_unique_number`). 50 intentos aleatorios
    y si todos chocan, ValueError. El EAN-13 es "770" + "0123" + numero_producto
    + dígito de control.
    """

    def setUp(self):
        self.company_a, self.creador_a = make_company(
            nombre="tiendaA", email="a@test.com", nit="900001")
        self.tipo_a = make_tipo(self.company_a, self.creador_a)
        self.company_b, self.creador_b = make_company(
            nombre="tiendaB", email="b@test.com", nit="900002")
        self.tipo_b = make_tipo(self.company_b, self.creador_b)

    def _producto(self, company, creador, tipo, numero=None, nombre="P"):
        """Crea un producto con numero_producto fijo (si se pasa) sin disparar la
        tarea de barras: los on_commit no corren en TestCase."""
        return ProductModel.objects.create(
            nombre=nombre, tipo_producto=tipo, detalles="x",
            valor_mayor=Decimal("500"), valor=Decimal("1000"),
            unidades_disponibles=10, tienda=company, creado_por=creador,
            **({"numero_producto": numero} if numero else {}),
        )

    def _con_codigo(self, company, creador, tipo, numero, nombre="P"):
        p = self._producto(company, creador, tipo, numero, nombre)
        generar_codigo_barras_task.delay(p.id)
        return Bar_codeModel.objects.get(product=p)

    def test_numero_producto_rango_5_digitos(self):
        for _ in range(50):
            p = ProductModel(
                nombre="X", tipo_producto=self.tipo_a, detalles="x",
                valor_mayor=Decimal("500"), valor=Decimal("1000"),
                unidades_disponibles=1, tienda=self.company_a,
                creado_por=self.creador_a,
            )
            n = p.generate_unique_number()
            self.assertEqual(len(n), 5)
            self.assertTrue(10000 <= int(n) <= 99999)

    def test_unicidad_es_por_tienda(self):
        # El mismo numero_producto puede existir en dos tiendas: no hay unique global.
        self._producto(self.company_a, self.creador_a, self.tipo_a, "12345", "A")
        self._producto(self.company_b, self.creador_b, self.tipo_b, "12345", "B")
        self.assertEqual(
            ProductModel.objects.filter(numero_producto="12345").count(), 2
        )

        # generate_unique_number solo mira la tienda propia: para la tienda B
        # (que no tiene el 54321) el "12345" está libre.
        self._producto(self.company_a, self.creador_a, self.tipo_a, "54321", "A2")
        p_b = ProductModel(
            nombre="B2", tipo_producto=self.tipo_b, detalles="x",
            valor_mayor=Decimal("500"), valor=Decimal("1000"),
            unidades_disponibles=1, tienda=self.company_b, creado_por=self.creador_b,
        )
        with mock.patch("apps.colletion.models.random.randint", return_value=54321):
            self.assertEqual(p_b.generate_unique_number(), "54321")

    def test_tope_por_tienda_agotado_lanza_valueerror(self):
        # Tope duro: 90.000 productos por tienda (10000-99999). Aquí se simula el
        # espacio agotado forzando a randint a devolver siempre un número ya usado.
        self._producto(self.company_a, self.creador_a, self.tipo_a, "55555", "A")
        p = ProductModel(
            nombre="Nuevo", tipo_producto=self.tipo_a, detalles="x",
            valor_mayor=Decimal("500"), valor=Decimal("1000"),
            unidades_disponibles=1, tienda=self.company_a, creado_por=self.creador_a,
        )
        with mock.patch("apps.colletion.models.random.randint",
                        return_value=55555) as m:
            with self.assertRaises(ValueError):
                p.generate_unique_number()
        self.assertEqual(m.call_count, 50)  # presupuesto de reintentos

    def test_ean13_estructura_y_digito_de_control(self):
        cb = self._con_codigo(self.company_a, self.creador_a, self.tipo_a, "24680")
        self.assertEqual(len(cb.code), 13)
        self.assertTrue(cb.code.isdigit())
        self.assertEqual(cb.code[:12], "7700123" + "24680")
        self.assertEqual(int(cb.code[12]), ean13_check_digit(cb.code[:12]))

    def test_ean13_no_es_unico_entre_tiendas(self):
        # LIMITACIÓN: numero_producto es único solo por tienda y el EAN-13 no
        # incluye la tienda (prefijo fijo 7700123). Dos tiendas distintas con el
        # mismo numero_producto producen el MISMO código de barras.
        code_a = self._con_codigo(self.company_a, self.creador_a, self.tipo_a, "77777", "A").code
        code_b = self._con_codigo(self.company_b, self.creador_b, self.tipo_b, "77777", "B").code
        self.assertEqual(code_a, code_b)
        # Y ambas filas conviven: Bar_codeModel.code no tiene unique.
        self.assertEqual(Bar_codeModel.objects.filter(code=code_a).count(), 2)
