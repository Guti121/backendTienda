import string
from tokenize import String
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
from apps.base.api.user.viewsPermissions import IsAdminOrCreator
import base64


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
        usuario_type = request.data.get("type_user")

        # Verificar permisos
        if not hasattr(user, "profile") or user.profile.tipo_usuario not in ["admin", "creator"]:
            return Response({"error": "No tienes permisos para generar un QR"}, status=status.HTTP_403_FORBIDDEN)

        company = getattr(user.profile, "company", None)
        if not company:
            return Response({"error": "No se encontró la empresa asociada al usuario"}, status=status.HTTP_404_NOT_FOUND)

        # Crear el token JWT
        token = AccessToken()
        print(token,'token qr')
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
        print(token)
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
            print(access_token,company_id,email,usuario_type,user)
            
            if user.email != email:
                    return Response({"error":'Este Qr no pertenece a este Aliado'},status=status.HTTP_403_FORBIDDEN)
            

        except Exception as e:
            error_message = "Token inválido o expirado"
            if "Token has expired" in str(e):
                error_message = "El token ha expirado"

            return Response({"error": error_message}, status=status.HTTP_403_FORBIDDEN)
        

        if company_owner(user):
            print('tiene compañia')
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
            usuario_type = token_data["type_user"]

            profile.company_id = company_id

            # Assuming token_data["type_user"] is an int
            if usuario_type == 1:
                profile.tipo_usuario = 'worker'
            elif usuario_type == 2:
                profile.tipo_usuario = 'admin'
            

            profile.save()
            return True

        except CustomUser.DoesNotExist:
            print("User not found")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
