
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
from rest_framework.authentication import TokenAuthentication

from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.authentication import JWTAuthentication

from pyzbar.pyzbar import decode
from PIL import Image
import io

class LecturaCodigoBarrasAPIView(APIView):
    permission_classes = [IsAuthenticated,IsWorkerOrCreator]
    authentication_classes = [JWTAuthentication]  

    def post(self, request):
        # Verificar que hay un archivo de imagen en los datos
        if 'imagen' not in request.FILES:
            return Response({'error': 'No se envió una imagen válida'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Leer la imagen desde el archivo subido
            imagen = request.FILES['imagen']
            cantidad = request.data.get('cantidad', 1)

            # Convertir la imagen a un objeto PIL para procesarla
            imagen_pil = Image.open(io.BytesIO(imagen.read()))

            # Decodificar la imagen utilizando pyzbar
            codigos = decode(imagen_pil)

            # Extraer los datos de los códigos de barras encontrados, si los hay
            datos_codigos = [codigo.data.decode("utf-8") for codigo in codigos]

            # Si no se encontraron códigos, retornar un mensaje apropiado
            if not datos_codigos:
                return Response({'mensaje': 'No se encontraron códigos de barras en la imagen'}, status=status.HTTP_400_BAD_REQUEST)

            # Buscar en la base de datos el código de barras
            company = company_owner(self.request.user)
            barcode = Bar_codeModel.objects.filter(code=datos_codigos[0],tienda=company).first()

            if barcode:
                producto = barcode.product
                if producto.disponible and int(producto.unidades_disponibles) >= int(cantidad):
                    # Retorna el producto o cualquier detalle que necesites del producto
                    return Response({
                        'mensaje': 'Código de barras encontrado',
                        'producto': {
                            'nombre': producto.nombre,  # Asegúrate de que el campo exista en el modelo ProductModel
                            'codigo':producto.numero_producto,
                            'cantidad': producto.unidades_disponibles,  # Otro campo de ejemplo
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({'error': 'No se encuentra disponible ese stock del producto'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'mensaje': 'Código de barras no encontrado'}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            # En caso de error, retornar un mensaje de error
            return Response({'error': f'Ocurrió un error al procesar la imagen: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class LecturaCodigoBarrasTextAPIView(APIView):
    permission_classes = [IsAuthenticated,IsWorkerOrCreator]
    authentication_classes = [JWTAuthentication]  
    serializerClass = ProductModelFilterSerializer# Aquí se define el serializador

    def post(self, request):
        try:
            # Leer la imagen desde el archivo subido
            codigoBarras = request.data.get('codigoBarras')
            cantidad = request.data.get('cantidad', 1)

            # Si no se encontraron códigos, retornar un mensaje apropiado
            if not codigoBarras:
                return Response({'mensaje': 'No se encontraron códigos de barras en la imagen'}, status=status.HTTP_400_BAD_REQUEST)

            # Buscar en la base de datos el código de barras
            company = company_owner(self.request.user)
            
            barcode = Bar_codeModel.objects.filter(code=codigoBarras,tienda = company).first()

            if barcode:
                producto = barcode.product
                if producto.disponible and int(producto.unidades_disponibles) >= int(cantidad):
                    # Serializar el producto con el serializador adecuado
                    serializer = self.serializerClass(producto)

                    # Retornar la respuesta con los datos serializados
                    return Response(serializer.data, status=status.HTTP_200_OK)
                else:
                    return Response({'error': 'No se encuentra disponible ese stock del producto'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'mensaje': 'Código de barras no encontrado'}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            # En caso de error, retornar un mensaje de error
            return Response({'error': f'Ocurrió un error al procesar el codigo de barras'})
        

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