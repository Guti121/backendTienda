# Descuentos: % general de la factura + % por línea, y `Factura.subtotal`
# (suma de líneas ya con su propio descuento, antes del % general). Las filas
# existentes no tenían descuento: `subtotal` se rellena con el `total` actual
# antes de volverlo NOT NULL.

from decimal import Decimal

import django.core.validators
from django.db import migrations, models
from django.db.models import F


def backfill_subtotal(apps, schema_editor):
    Factura = apps.get_model("shoppingcart", "Factura")
    Factura.objects.filter(subtotal__isnull=True).update(subtotal=F("total"))


class Migration(migrations.Migration):

    dependencies = [
        ('shoppingcart', '0004_facturadetalle_fd_tienda_creado_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='factura',
            name='subtotal',
            field=models.DecimalField(decimal_places=0, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='factura',
            name='descuento_porcentaje',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('0'), max_digits=5,
                validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)],
            ),
        ),
        migrations.AddField(
            model_name='facturadetalle',
            name='descuento_porcentaje',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('0'), max_digits=5,
                validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)],
            ),
        ),
        migrations.RunPython(backfill_subtotal, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='factura',
            name='subtotal',
            field=models.DecimalField(decimal_places=0, max_digits=10),
        ),
    ]
