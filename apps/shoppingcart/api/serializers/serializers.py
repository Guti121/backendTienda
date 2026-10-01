from decimal import Decimal
from rest_framework import serializers
from ...models import Factura, FacturaDetalle
from apps.base.api.fields import redondear_pesos
from apps.colletion.models import DescuentoProducto, ProductModel
from django.utils import timezone
from babel.numbers import format_currency


class ProductoSerializer(serializers.ModelSerializer):
    valor_cop=serializers.SerializerMethodField()

    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'valor_cop']

    def get_valor_cop(self,obj):
        
        return format_currency(obj.valor,'COP',locale='es_CO')

#Serializador para listar sin detalles
class FacturaListSerializer(serializers.ModelSerializer):
    total_cop  = serializers.SerializerMethodField()

    class Meta:
        model = Factura
        fields = ['id', 'fecha','total_cop','descuento_porcentaje','metodo_pago']


    def get_total_cop (self, obj):
        # Formatea el valor de `total` como COP usando format_currency
        return format_currency(obj.total, 'COP', locale='es_CO')


class FacturaDetalleSerializer(serializers.ModelSerializer):
    producto = ProductoSerializer()
    subtotal_cop  = serializers.SerializerMethodField()


    class Meta:
        model = FacturaDetalle
        fields = ['id', 'nombre_producto','producto', 'cantidad','valor_und' ,'subtotal_cop','descuento_porcentaje']


    def get_subtotal_cop (self, obj):
        # Formatea el valor de `total` como COP usando format_currency
        return format_currency(obj.subtotal, 'COP', locale='es_CO')




class FacturaSerializer(serializers.ModelSerializer):
    detalles = FacturaDetalleSerializer(many=True)
    subtotal_cop = serializers.SerializerMethodField()
    total_cop  = serializers.SerializerMethodField()
    creado_por_full_name = serializers.SerializerMethodField()
    tienda_nombre = serializers.CharField(source='tienda.name', read_only=True)


    class Meta:
        model = Factura
        fields = ['id', 'fecha','tienda_nombre','creado_por_full_name', 'subtotal_cop', 'total_cop', 'descuento_porcentaje', 'metodo_pago', 'detalles']


    def get_subtotal_cop(self, obj):
        return format_currency(obj.subtotal, 'COP', locale='es_CO')

    def get_total_cop (self, obj):
        # Formatea el valor de `total` como COP usando format_currency
        return format_currency(obj.total, 'COP', locale='es_CO')

    def get_creado_por_full_name(self, obj):
        if obj.creado_por:
            return f"{obj.creado_por.first_name} {obj.creado_por.last_name}"
        return None


class FacturaDetalleCreateSerializer(serializers.ModelSerializer):
    # Sin default: si no viene, queda ausente de validated_data (distinto de
    # "vino 0"), para poder resolver el fallback a la promo del producto.
    descuento_porcentaje = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, min_value=0, max_value=100
    )

    class Meta:
        model = FacturaDetalle
        fields = ['producto', 'cantidad', 'descuento_porcentaje']

class FacturaCreateSerializer(serializers.ModelSerializer):

    detalles = FacturaDetalleCreateSerializer(many=True)  # Permitimos múltiples detalles
    descuento_porcentaje = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, default=Decimal("0"),
        min_value=0, max_value=100,
    )
    metodo_pago = serializers.ChoiceField(
        choices=Factura.METODO_PAGO_CHOICES, required=False, default="efectivo",
    )

    class Meta:
        model = Factura
        fields = ['detalles', 'descuento_porcentaje', 'metodo_pago']  # Los campos a incluir


    def create(self, validated_data):
        # Extraemos los detalles y el % de descuento general de la venta
        detalles_data = validated_data.pop('detalles')
        descuento_factura_pct = validated_data.pop('descuento_porcentaje', Decimal('0'))

        # Promos vigentes de todos los productos de la venta, en una sola query
        # (nunca una por línea).
        producto_ids = [d['producto'].id for d in detalles_data]
        now = timezone.now()
        promos_vigentes = {
            d.producto_id: d.porcentaje
            for d in DescuentoProducto.objects.filter(
                producto_id__in=producto_ids, activo=True,
                fecha_inicio__lte=now, fecha_fin__gte=now,
            )
        }

        validated_data['subtotal'] = Decimal('0')
        validated_data['total'] = Decimal('0')
        validated_data['descuento_porcentaje'] = descuento_factura_pct
        # Crear la factura con la fecha y hora actual
        validated_data['fecha'] = timezone.now()  # Asignamos la fecha y hora actual
        factura = Factura.objects.create(**validated_data)

        subtotal_factura = Decimal('0')

        # Crear los detalles de la factura
        for detalle_data in detalles_data:
            # Obtener el producto utilizando el producto desde el detalle
            producto = detalle_data['producto']
            cantidad = detalle_data['cantidad']

            # Asegúrate de que el producto sea un objeto ProductModel
            if not isinstance(producto, ProductModel):
                raise serializers.ValidationError("El producto no es válido.")

            # % de esta línea: el override si vino explícito (incluido 0),
            # si no la promo vigente del producto, si no 0.
            override = detalle_data.get('descuento_porcentaje')
            pct_linea = override if override is not None else promos_vigentes.get(producto.id, Decimal('0'))

            precio_lista_linea = Decimal(producto.valor) * cantidad
            subtotal = redondear_pesos(precio_lista_linea * (1 - pct_linea / 100))

            # Crear el detalle de la factura
            FacturaDetalle.objects.create(
                factura=factura,
                producto=producto,  # Asignamos el objeto Producto
                cantidad=cantidad,
                subtotal=subtotal,  # Asumiendo que tienes un campo subtotal en FacturaDetalle
                descuento_porcentaje=pct_linea,
                tienda=factura.tienda,  # ← Se pasa la tienda de la factura
                creado_por=factura.creado_por,  # ← Se asigna el creador

            )

            subtotal_factura += subtotal  # Acumulamos el subtotal

        # Descuento general de la venta sobre el subtotal ya neto de descuentos
        # por línea.
        factura.subtotal = subtotal_factura
        factura.total = redondear_pesos(subtotal_factura * (1 - descuento_factura_pct / 100))
        factura.save()

        return factura


class ProductModelFilterSerializer(serializers.ModelSerializer):
    # Serializador para el producto y su categoría (tipo_producto)
    tipo_producto = serializers.CharField(source='tipo_producto.tipo_producto', read_only=True)
    categoria = serializers.CharField(
        source='tipo_producto.categoria.nombre', read_only=True, default=None,
    )
    descuento_porcentaje = serializers.SerializerMethodField()
    valor_con_descuento = serializers.SerializerMethodField()

    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'tipo_producto', 'categoria', 'detalles', 'valor', 'unidades_disponibles',
                  'descuento_porcentaje', 'valor_con_descuento']

    def _promo_vigente(self, obj):
        # Lookup de un solo producto (un escaneo = un producto): una query
        # propia acá es aceptable, no hay lista que prefetchear.
        now = timezone.now()
        return DescuentoProducto.objects.filter(
            producto=obj, activo=True, fecha_inicio__lte=now, fecha_fin__gte=now
        ).first()

    def get_descuento_porcentaje(self, obj):
        promo = self._promo_vigente(obj)
        return promo.porcentaje if promo else Decimal('0')

    def get_valor_con_descuento(self, obj):
        pct = self.get_descuento_porcentaje(obj)
        if not pct:
            return obj.valor
        return redondear_pesos(obj.valor * (1 - pct / 100))

    def to_representation(self, instance):
        """
        Modifica la representación del serializador para agregar más lógica
        (por ejemplo, si necesitas formatear algún campo o agregar un dato extra).
        """
        representation = super().to_representation(instance)

        # Puedes agregar más lógica si es necesario (ejemplo: formatear valores o agregar más datos)
        return representation
