"""Siembra muchos productos publicados en una tienda para probar el catálogo
con volumen (grid, filtros, scroll). Marca lo que crea con `[bulk]` en
`detalles` para poder limpiarlo con --reset.

    python manage.py seed_bulk_products --store electrostore --count 70
    python manage.py seed_bulk_products --store electrostore --reset
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.colletion.models import ProductModel, TypeProductModel
from apps.myStore.models import Company

MARKER = "[bulk]"

CATEGORIAS = [
    "Electrónica", "Accesorios", "Hogar", "Audio",
    "Cómputo", "Gaming", "Cables", "Iluminación",
]

ADJ = [
    "Pro", "Ultra", "Max", "Lite", "Plus", "Mini", "Slim", "Smart",
    "Premium", "Clásico", "Compacto", "Portátil", "Inalámbrico",
]
NOMBRES = [
    "Audífonos", "Parlante", "Teclado", "Mouse", "Monitor", "Cámara web",
    "Micrófono", "Cargador", "Batería externa", "Hub USB", "Cable HDMI",
    "Adaptador", "Soporte", "Lámpara LED", "Tira LED", "Ventilador",
    "Router", "Repetidor WiFi", "Disco SSD", "Memoria USB", "Tarjeta SD",
    "Control", "Base refrigerante", "Webcam 4K", "Kit de limpieza",
    "Organizador", "Regleta", "Timbre inteligente", "Foco inteligente",
    "Sensor de movimiento",
]
FRASES = [
    "Ideal para el día a día.", "Diseño moderno y resistente.",
    "Alta compatibilidad.", "Fácil de instalar.",
    "Bajo consumo de energía.", "Materiales de primera calidad.",
    "Garantía de la tienda.", "Edición limitada.",
]


class Command(BaseCommand):
    help = "Crea productos de prueba en una tienda para ver el catálogo con volumen."

    def add_arguments(self, parser):
        parser.add_argument("--store", default="electrostore")
        parser.add_argument("--count", type=int, default=70)
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra los productos [bulk] de esa tienda y sale.",
        )

    def handle(self, *args, **opts):
        try:
            company = Company.objects.get(name__iexact=opts["store"])
        except Company.DoesNotExist:
            raise CommandError(f"No existe la tienda '{opts['store']}'.")

        creador = company.creator_user

        bulk_qs = ProductModel.objects.filter(
            tienda=company, detalles__startswith=MARKER
        )

        if opts["reset"]:
            n = bulk_qs.count()
            for p in bulk_qs:
                p.delete()
            self.stdout.write(self.style.SUCCESS(f"Borrados {n} productos [bulk] de {company.name}."))
            return

        # Asegura categorías.
        tipos = []
        for nombre in CATEGORIAS:
            t, _ = TypeProductModel.objects.get_or_create(
                tienda=company,
                tipo_producto=nombre.capitalize(),
                defaults={"creado_por": creador},
            )
            tipos.append(t)

        count = opts["count"]
        creados = 0
        for _ in range(count):
            nombre = f"{random.choice(NOMBRES)} {random.choice(ADJ)} {random.randint(100, 999)}"
            valor_mayor = Decimal(random.randrange(5_000, 400_000, 500))
            margen = Decimal(str(round(random.uniform(1.25, 2.3), 2)))
            valor = (valor_mayor * margen).quantize(Decimal("1"))
            valor = (valor // 500 + 1) * 500  # redondeo comercial

            # stock: la mayoría medio, algunos bajos, unos pocos muy altos
            r = random.random()
            if r < 0.15:
                stock = random.randint(1, 6)
            elif r < 0.9:
                stock = random.randint(10, 180)
            else:
                stock = random.randint(200, 900)

            try:
                with transaction.atomic():
                    p = ProductModel.objects.create(
                        tienda=company,
                        creado_por=creador,
                        nombre=nombre,
                        tipo_producto=random.choice(tipos),
                        detalles=f"{MARKER} {random.choice(FRASES)}",
                        valor_mayor=valor_mayor,
                        valor=valor,
                        valor_costos_fijos=Decimal("0"),
                        unidades_disponibles=stock,
                        disponible=True,
                        publicar=True,
                    )
                # Envejece ~65% para que solo algunos salgan como "Nuevo".
                if random.random() < 0.65:
                    dias = random.randint(20, 420)
                    ProductModel.objects.filter(pk=p.pk).update(
                        creado_en=timezone.now() - timedelta(days=dias)
                    )
                creados += 1
            except Exception as e:  # noqa: BLE001 - seguir aunque uno falle
                self.stderr.write(f"  saltado: {e}")

        total_pub = ProductModel.objects.filter(
            tienda=company, publicar=True, disponible=True
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Creados {creados} productos [bulk] en '{company.name}'. "
                f"Total publicados y disponibles ahora: {total_pub}. "
                f"Categorías: {len(tipos)}."
            )
        )
