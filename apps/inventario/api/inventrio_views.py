from rest_framework.response import Response
from rest_framework import status

from rest_framework.generics import ListAPIView
from apps.colletion.models import ProductModel
from babel.numbers import format_currency

from apps.inventario.api.serializers.serializer import InventarioListFilterSerializer
#Vista para realizar el inventario actual 
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.base.api.user.viewsPermissions import isCreator


class InventarioView(ListAPIView):
    authentication_classes = [JWTAuthentication]  # Agrega JWTAuthentication
    permission_classes = [IsAuthenticated,isCreator]  # Agrega IsAuthenticated
   

    def post(self, request, *args, **kwargs):
        productos = ProductModel.objects.filter(disponible=True)
        print(productos)
        valor_x_mayor = 0.0
        valor_detal = 0.0
        valor_total_producto = 0.0
        numero_productos = 0

        # Sumamos los valores de los productos
        for producto in productos:
            #valor total productos x mayor
            valor_x_mayor += producto.unidades_disponibles * float(producto.valor_mayor)
            valor_detal  += producto.unidades_disponibles * float(producto.valor) 
            numero_productos +=producto.unidades_disponibles

        # Calculamos la ganancia total
        
        valor_ganancia = valor_detal - valor_x_mayor
        

        # Formatear los valores a COP
        valor_x_mayor_cop = format_currency(valor_x_mayor, 'COP', locale='es_CO')
        valor_detal_cop = format_currency(valor_detal, 'COP', locale='es_CO')
        valor_ganancia_cop = format_currency(valor_ganancia, 'COP', locale='es_CO')

        # Retornamos los resultados
        return Response({
            'Numero de Total de Productos':numero_productos,
            'Valor x Mayor productos ': valor_x_mayor_cop,
            'valor Total Producto sin ganancia': valor_detal_cop,
            'valor Total de ganancias': valor_ganancia_cop
        },status=status.HTTP_200_OK)
    


class InventarioViewFilter(ListAPIView):
    authentication_classes = [JWTAuthentication]  # Agrega JWTAuthentication
    permission_classes = [IsAuthenticated,isCreator]  # Agrega IsAuthenticated

    def post(self, request, *args, **kwargs):
       
        # Validamos los datos con el serializer
        serializer = InventarioListFilterSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            # Accedemos a los valores validados
            filter_value = serializer.validated_data['filter']
            valor_value = serializer.validated_data['valor']

        # Inicializamos las variables para el cálculo
        valor_x_mayor = 0.0
        valor_detal = 0.0
        numero_productos = 0
        # Usamos un diccionario para pasar el filtro dinámicamente
        filter_kwargs = {f"{filter_value}": valor_value}

        # Filtrar los productos usando el valor dinámico
        productos = ProductModel.objects.filter(**filter_kwargs)

        # Ahora calculamos las ganancias
        for producto in productos:
            valor_x_mayor += producto.unidades_disponibles *float(producto.valor_mayor)
            valor_detal += producto.unidades_disponibles * float(producto.valor)
            numero_productos+= producto.unidades_disponibles
        # Cálculo de la ganancia
        valor_ganancia = valor_detal - valor_x_mayor
         # Formatear los valores a COP
        valor_x_mayor_cop = format_currency(valor_x_mayor, 'COP', locale='es_CO')
        valor_detal_cop = format_currency(valor_detal, 'COP', locale='es_CO')
        valor_ganancia_cop = format_currency(valor_ganancia, 'COP', locale='es_CO')


        # Retornar los resultados en la respuesta
        return Response({
            'productos': filter_value,  # Cantidad de productos
            'Numero de Productos':numero_productos,
            'valor x mayor': valor_x_mayor_cop,
            'valor detal': valor_detal_cop,
            'Ganancia total': valor_ganancia_cop
        }, status=status.HTTP_200_OK)
