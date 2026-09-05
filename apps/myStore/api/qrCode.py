from django.http import HttpResponse
from Tienda_Virtual.globalFunctions import company_owner
from apps.base.models import CustomUser
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken
from datetime import timedelta
import qrcode
import io
import json
import logging
from apps.base.api.user.viewsPermissions import IsAdminOrCreator
import base64

logger = logging.getLogger(__name__)


class GenerarQRView(APIView):
    """
    Vista para generar un código QR con información del usuario y su empresa.
    Solo los usuarios autenticados con permisos de 'admin' o 'creator' pueden generar un QR.
    # """
   
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]

    def post(self, request, *args, **kwargs):
        """
        Genera un código QR con un token JWT que contiene información de la empresa y el usuario.
        """
        user = request.user
        usuario_email = request.data.get("email")

        # type_user viaja como 1 (worker) o 2 (admin). Llega como string desde el
        # cliente; lo normalizamos a int aquí para no arrastrar el bug de comparar
        # "1" == 1 (siempre falso) al afiliar al usuario.
        try:
            usuario_type = int(request.data.get("type_user"))
        except (TypeError, ValueError):
            usuario_type = None
        if usuario_type not in (1, 2):
            return Response(
                {"error": "type_user inválido. Usa 1 (trabajador) o 2 (administrador)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar permisos
        if not hasattr(user, "profile") or user.profile.tipo_usuario not in ["admin", "creator"]:
            return Response({"error": "No tienes permisos para generar un QR"}, status=status.HTTP_403_FORBIDDEN)

        company = getattr(user.profile, "company", None)
        if not company:
            return Response({"error": "No se encontró la empresa asociada al usuario"}, status=status.HTTP_404_NOT_FOUND)

        # Crear el token JWT
        token = AccessToken()
        token["company"] = str(company.id)
        token["email"] = usuario_email
        token["type_user"] = usuario_type
        token.set_exp(lifetime=timedelta(minutes=5))

        # Datos del QR
        qr_data = json.dumps({
            "company_id": str(company.id),
            "email": usuario_email,
            "type": usuario_type,
            "token": str(token)
        })
        # Generar el QR y convertirlo en base64
        qr = qrcode.make(qr_data)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return Response({"qr_base64": img_base64}, status=status.HTTP_201_CREATED)
    
class LeerQRView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = request.GET.get("token")
        

        if not token:
            return Response({"error": "Token faltante"}, status=400)

        try:
            access_token = AccessToken(token)
            company_id = access_token["company"]
            email = access_token["email"]
            usuario_type = access_token["type_user"]
            user= request.user

            if user.email != email:
                    return Response({"error":'Este Qr no pertenece a este Aliado'},status=status.HTTP_403_FORBIDDEN)
            

        except Exception as e:
            error_message = "Token inválido o expirado"
            if "Token has expired" in str(e):
                error_message = "El token ha expirado"

            return Response({"error": error_message}, status=status.HTTP_403_FORBIDDEN)
        

        if company_owner(user):
            return Response({"error":'El usuario ya esta afiliado a una compañia'},status=status.HTTP_403_FORBIDDEN)
       
        else:
            if self.add_user_company(user.email,email,token):
                return Response({
                    "message": "QR leído correctamente,verifica tu perfil",
                }, status=status.HTTP_200_OK)
            
            else: 
                return Response({ "message": "Error No sabemos"},status=status.HTTP_403_FORBIDDEN)

    def add_user_company(self, user_email, token_email, token):
        if user_email != token_email:
            return False

        try:
            user = CustomUser.objects.get(email=user_email)
            profile = user.profile  # OneToOneField

            token_data = AccessToken(token)
            company_id = token_data["company"]

            try:
                usuario_type = int(token_data["type_user"])
            except (TypeError, ValueError, KeyError):
                usuario_type = None

            tipos = {1: 'worker', 2: 'admin'}
            if usuario_type not in tipos:
                logger.warning("type_user inválido en el token QR: %r", token_data.get('type_user'))
                return False

            profile.company_id = company_id
            profile.tipo_usuario = tipos[usuario_type]
            profile.save()
            return True

        except CustomUser.DoesNotExist:
            logger.warning("add_user_company: usuario %s no encontrado", user_email)
            return False
        except Exception:
            logger.exception("add_user_company: error inesperado")
            return False
