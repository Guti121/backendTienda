from django.core.management.base import BaseCommand

from apps.colletion.models import ProductModel
from apps.colletion.tasks import generar_codigo_barras_task


class Command(BaseCommand):
    help = "Genera el código de barras de los productos que no tengan uno."

    def add_arguments(self, parser):
        parser.add_argument(
            '--sync', action='store_true',
            help="Genera en el acto en vez de encolar en Celery.",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Solo lista los productos afectados, sin generar nada.",
        )

    def handle(self, *args, **options):
        # producto__isnull=True -> productos sin Bar_codeModel (reverse OneToOne).
        pendientes = ProductModel.objects.filter(producto__isnull=True).order_by('id')
        total = pendientes.count()

        if not total:
            self.stdout.write(self.style.SUCCESS("Todos los productos tienen código de barras."))
            return

        self.stdout.write(f"{total} producto(s) sin código de barras.")

        if options['dry_run']:
            for p in pendientes:
                self.stdout.write(f"  - #{p.id} {p.nombre} (tienda: {p.tienda_id})")
            return

        hechos = 0
        for p in pendientes.iterator():
            if options['sync']:
                p.crear_codigo_barras()
            else:
                generar_codigo_barras_task.delay(p.id)
            hechos += 1

        verbo = "generados" if options['sync'] else "encolados"
        self.stdout.write(self.style.SUCCESS(f"{hechos} código(s) de barras {verbo}."))
