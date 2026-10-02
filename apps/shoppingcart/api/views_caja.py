from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from Tienda_Virtual.globalFunctions import company_owner
from apps.base.api.user.viewsPermissions import IsAdminOrCreator, IsWorkerOrCreator
from apps.myStore.models import Company
from apps.shoppingcart.models import CajaModel, Factura, MovimientoCajaModel
from .serializers.serializers_caja import (
    CajaAbrirSerializer,
    CajaCerrarSerializer,
    CajaSerializer,
    MovimientoCajaSerializer,
)


def _resumen_caja(caja):
    """Desglose en vivo de una caja: solo 'efectivo' suma al esperado (los
    demás métodos de pago no mueven el cajón físico)."""
    ventas = (
        Factura.objects.filter(caja=caja)
        .values('metodo_pago')
        .annotate(total=Coalesce(Sum('total'), Decimal('0')))
    )
    por_metodo = {v['metodo_pago']: v['total'] for v in ventas}
    ventas_efectivo = por_metodo.pop('efectivo', Decimal('0'))

    ingresos = (
        MovimientoCajaModel.objects.filter(caja=caja, tipo='ingreso')
        .aggregate(t=Coalesce(Sum('monto'), Decimal('0')))['t']
    )
    retiros = (
        MovimientoCajaModel.objects.filter(caja=caja, tipo='retiro')
        .aggregate(t=Coalesce(Sum('monto'), Decimal('0')))['t']
    )
    esperado = caja.monto_apertura + ventas_efectivo + ingresos - retiros

    return {
        'monto_apertura': caja.monto_apertura,
        'ventas_efectivo': ventas_efectivo,
        # Informativo: lo vendido por los demás métodos no afecta el esperado.
        'ventas_otros_metodos': por_metodo,
        'ingresos': ingresos,
        'retiros': retiros,
        'esperado_en_caja': esperado,
        'numero_de_facturas': Factura.objects.filter(caja=caja).count(),
    }


class CajaAbrirView(CreateAPIView):
    serializer_class = CajaAbrirSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsWorkerOrCreator]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = company_owner(request.user)

        with transaction.atomic():
            # `CajaModel` no tiene filas si no hay ninguna caja abierta, así
            # que no hay nada que lockear ahí para evitar dos "abrir" en
            # paralelo (el lock solo sirve sobre filas que ya existen). Se
            # lockea la fila de la tienda (que siempre existe) para serializar
            # a dos requests concurrentes de la misma tienda.
            Company.objects.select_for_update().get(pk=company.pk)

            if CajaModel.objects.filter(tienda=company, cerrada_en__isnull=True).exists():
                return Response(
                    {"error": "Ya hay una caja abierta."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            caja = CajaModel.objects.create(
                monto_apertura=serializer.validated_data['monto_apertura'],
                tienda=company,
                creado_por=request.user,
            )

        return Response(CajaSerializer(caja).data, status=status.HTTP_201_CREATED)


class CajaActualView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsWorkerOrCreator]

    def get(self, request):
        company = company_owner(request.user)
        caja = CajaModel.objects.filter(tienda=company, cerrada_en__isnull=True).first()
        if not caja:
            return Response({"error": "No hay una caja abierta."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CajaSerializer(caja).data)


class CajaResumenView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsWorkerOrCreator]

    def get(self, request):
        company = company_owner(request.user)
        caja = CajaModel.objects.filter(tienda=company, cerrada_en__isnull=True).first()
        if not caja:
            return Response({"error": "No hay una caja abierta."}, status=status.HTTP_404_NOT_FOUND)
        data = _resumen_caja(caja)
        data['caja'] = CajaSerializer(caja).data
        return Response(data)


class CajaCerrarView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsWorkerOrCreator]

    def post(self, request):
        serializer = CajaCerrarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = company_owner(request.user)

        with transaction.atomic():
            caja = (
                CajaModel.objects.select_for_update()
                .filter(tienda=company, cerrada_en__isnull=True)
                .first()
            )
            if not caja:
                return Response({"error": "No hay una caja abierta."}, status=status.HTTP_404_NOT_FOUND)

            resumen = _resumen_caja(caja)
            caja.monto_cierre_declarado = serializer.validated_data['monto_cierre_declarado']
            caja.monto_cierre_esperado = resumen['esperado_en_caja']
            caja.diferencia = caja.monto_cierre_declarado - caja.monto_cierre_esperado
            caja.nota_cierre = serializer.validated_data.get('nota_cierre', '')
            caja.cerrada_en = timezone.now()
            caja.cerrada_por = request.user
            caja.save()

        resumen['caja'] = CajaSerializer(caja).data
        return Response(resumen, status=status.HTTP_200_OK)


class MovimientoCajaCreateView(CreateAPIView):
    serializer_class = MovimientoCajaSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsWorkerOrCreator]

    def create(self, request, *args, **kwargs):
        company = company_owner(request.user)
        caja = CajaModel.objects.filter(tienda=company, cerrada_en__isnull=True).first()
        if not caja:
            return Response({"error": "No hay una caja abierta."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(caja=caja, tienda=company, creado_por=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CajaHistorialListView(ListAPIView):
    serializer_class = CajaSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrCreator]

    def get_queryset(self):
        company = company_owner(self.request.user)
        return (
            CajaModel.objects.filter(tienda=company, cerrada_en__isnull=False)
            .order_by('-creado_en')
        )
