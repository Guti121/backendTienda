import logging

from apps.shoppingcart.api.serializers.serializersBarCode import BarCodeSerializer
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from Tienda_Virtual.globalFunctions import company_owner
from apps.base.api.user.viewsPermissions import IsWorkerOrCreator
from apps.shoppingcart.api.serializers.serializers import ProductModelFilterSerializer
from apps.colletion.models import Bar_codeModel
from rest_framework.permissions import IsAuthenticated

from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.authentication import JWTAuthentication

from pyzbar.pyzbar import decode
from PIL import Image
import io

logger = logging.getLogger(__name__)


def _buscar_producto_por_codigo(company, code, cantidad_raw, serializer_class):
    """Lógica compartida por los dos lectores (imagen y texto): valida
    `cantidad`, busca el código en la tienda del usuario y revisa stock.
    Devuelve la Response final (200 con el producto, o 400 con el motivo).
    """
    try:
        cantidad = int(cantidad_raw)
    except (TypeError, ValueError):
        return Response({'error': 'La cantidad debe ser un número entero.'},
                        status=status.HTTP_400_BAD_REQUEST)
    if cantidad <= 0:
        return Response({'error': 'La cantidad debe ser mayor que 0.'},
                        status=status.HTTP_400_BAD_REQUEST)

    barcode = Bar_codeModel.objects.filter(code=code, tienda=company).first()
    if not barcode:
        return Response({'mensaje': 'Código de barras no encontrado'},
                        status=status.HTTP_400_BAD_REQUEST)

    producto = barcode.product
    if not producto.disponible or producto.unidades_disponibles < cantidad:
        return Response({'error': 'No se encuentra disponible ese stock del producto'},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response(serializer_class(producto).data, status=status.HTTP_200_OK)


class LecturaCodigoBarrasAPIView(APIView):
    permission_classes = [IsAuthenticated,IsWorkerOrCreator]
    authentication_classes = [JWTAuthentication]
    serializerClass = ProductModelFilterSerializer# Aquí se define el serializador

    def post(self, request):
        # Verificar que hay un archivo de imagen en los datos
        if 'imagen' not in request.FILES:
            return Response({'error': 'No se envió una imagen válida'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Leer la imagen y decodificarla con pyzbar
            imagen_pil = Image.open(io.BytesIO(request.FILES['imagen'].read()))
            codigos = decode(imagen_pil)
        except Exception:
            # Imagen corrupta/no soportada: es un problema del dato que mandó el
            # cliente (400), no del servidor. El detalle real queda en el log,
            # no se filtra en la respuesta.
            logger.exception("No se pudo procesar la imagen del código de barras")
            return Response({'error': 'No se pudo procesar la imagen.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Si no se encontraron códigos, retornar un mensaje apropiado
        if not codigos:
            return Response({'mensaje': 'No se encontraron códigos de barras en la imagen'}, status=status.HTTP_400_BAD_REQUEST)

        company = company_owner(self.request.user)
        return _buscar_producto_por_codigo(
            company, codigos[0].data.decode("utf-8"),
            request.data.get('cantidad', 1), self.serializerClass,
        )


class LecturaCodigoBarrasTextAPIView(APIView):
    permission_classes = [IsAuthenticated,IsWorkerOrCreator]
    authentication_classes = [JWTAuthentication]
    serializerClass = ProductModelFilterSerializer# Aquí se define el serializador

    def post(self, request):
        codigoBarras = request.data.get('codigoBarras')
        if not codigoBarras:
            return Response({'mensaje': 'Debes enviar un código de barras'}, status=status.HTTP_400_BAD_REQUEST)

        company = company_owner(self.request.user)
        return _buscar_producto_por_codigo(
            company, codigoBarras, request.data.get('cantidad', 1), self.serializerClass,
        )


#Retrieve barCode
class RetrieveBarCode(RetrieveAPIView):
    queryset = Bar_codeModel.objects.all()
    serializer_class = BarCodeSerializer
    lookup_field = 'pk'  # Usamos pk para la búsqueda
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        tienda = company_owner(user)  # Suponiendo que retorna la tienda del usuario

        if tienda:
            # Ahora buscamos el producto usando el pk y la tienda del usuario
            producto = get_object_or_404(
                Bar_codeModel,
                product__id=kwargs.get('pk'),  # Buscamos por el pk del producto relacionado
                product__tienda=tienda  # Aseguramos que el producto esté asociado a la tienda
            )
            serializer = self.get_serializer(producto)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({'error':'No encontramos tu tienda'}, status=status.HTTP_401_UNAUTHORIZED)
