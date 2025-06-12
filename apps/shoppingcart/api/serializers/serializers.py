from decimal import Decimal
from rest_framework import serializers
from ...models import Factura, FacturaDetalle
from apps.colletion.models import ProductModel
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
        fields = ['id', 'fecha','total_cop']


    def get_total_cop (self, obj):
        # Formatea el valor de `total` como COP usando format_currency
        return format_currency(obj.total, 'COP', locale='es_CO')

        
class FacturaDetalleSerializer(serializers.ModelSerializer):
    producto = ProductoSerializer()
    subtotal_cop  = serializers.SerializerMethodField()


    class Meta:
        model = FacturaDetalle
        fields = ['id', 'nombre_producto','producto', 'cantidad','valor_und' ,'subtotal_cop']

    
    def get_subtotal_cop (self, obj):
        # Formatea el valor de `total` como COP usando format_currency
        return format_currency(obj.subtotal, 'COP', locale='es_CO')
    



class FacturaSerializer(serializers.ModelSerializer):
    detalles = FacturaDetalleSerializer(many=True)
    total_cop  = serializers.SerializerMethodField()
    creado_por_full_name = serializers.SerializerMethodField()
    tienda_nombre = serializers.CharField(source='tienda.name', read_only=True)


    class Meta:
        model = Factura
        fields = ['id', 'fecha','tienda_nombre','creado_por_full_name', 'total_cop', 'detalles']

    
    def get_total_cop (self, obj):
        # Formatea el valor de `total` como COP usando format_currency
        return format_currency(obj.total, 'COP', locale='es_CO')

    def get_creado_por_full_name(self, obj):
        if obj.creado_por:
            return f"{obj.creado_por.first_name} {obj.creado_por.last_name}"
        return None
    

class FacturaDetalleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacturaDetalle
        fields = ['producto', 'cantidad']

class FacturaCreateSerializer(serializers.ModelSerializer):
    
    detalles = FacturaDetalleCreateSerializer(many=True)  # Permitimos múltiples detalles

    class Meta:
        model = Factura
        fields = ['detalles']  # Los campos a incluir


    def create(self, validated_data):
        # Extraemos los detalles
        detalles_data = validated_data.pop('detalles')

        total = Decimal('0.00')  # Inicializamos el total
        validated_data['total']=total
        # Crear la factura con la fecha y hora actual
        validated_data['fecha'] = timezone.now()  # Asignamos la fecha y hora actual
        factura = Factura.objects.create(**validated_data)

        # Crear los detalles de la factura
        for detalle_data in detalles_data:
            # Obtener el producto utilizando el producto desde el detalle
            producto = detalle_data['producto']
            cantidad = detalle_data['cantidad']
            
            # Asegúrate de que el producto sea un objeto ProductModel
            if not isinstance(producto, ProductModel):
                raise serializers.ValidationError("El producto no es válido.")

            # Calculamos el subtotal
            
            subtotal = Decimal(producto.valor) * cantidad

            # Crear el detalle de la factura
            FacturaDetalle.objects.create(
                factura=factura,
                producto=producto,  # Asignamos el objeto Producto
                cantidad=cantidad,
                subtotal=subtotal,  # Asumiendo que tienes un campo subtotal en FacturaDetalle
                tienda=factura.tienda,  # ← Se pasa la tienda de la factura
                creado_por=factura.creado_por,  # ← Se asigna el creador
                
            )

            total += subtotal  # Acumulamos el total

        # Asignamos el total calculado a la factura
        factura.total = total
        factura.save()  # Guardamos la factura con el total actualizado

        return factura


class ProductModelFilterSerializer(serializers.ModelSerializer):
    # Serializador para el producto y su categoría (tipo_producto)
    tipo_producto = serializers.CharField(source='tipo_producto.tipo_producto', read_only=True)

    class Meta:
        model = ProductModel
        fields = ['id', 'nombre', 'tipo_producto', 'detalles', 'valor', 'unidades_disponibles']
    
    def to_representation(self, instance):
        """
        Modifica la representación del serializador para agregar más lógica
        (por ejemplo, si necesitas formatear algún campo o agregar un dato extra).
        """
        representation = super().to_representation(instance)

        # Puedes agregar más lógica si es necesario (ejemplo: formatear valores o agregar más datos)
        return representation
