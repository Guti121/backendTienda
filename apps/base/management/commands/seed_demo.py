"""Puebla la BD con datos de demo para pruebas manuales / E2E.

    python manage.py seed_demo            # crea lo que falte (idempotente)
    python manage.py seed_demo --reset    # borra los datos demo antes de crear

Emails demo: *@demo.local, contraseña "demo12345".
"""
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.base.models import CustomUser, TipoUsuario, UserProfile
from apps.colletion.models import (
    Bar_codeModel, Config_ProductModel, ProductModel, TypeProductModel,
)
from apps.myStore.models import Company
from apps.shoppingcart.models import Factura, FacturaDetalle

PWD = "demo12345"
# PNG 1x1 para el logo (Company.url_logo no admite blank).
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6260000100000500010d0a2db4000000004945"
    "4e44ae426082"
)


def _user(email, first, last):
    u, created = CustomUser.objects.get_or_create(
        email=email,
        defaults=dict(username=email.split("@")[0], first_name=first, last_name=last),
    )
    if created:
        u.set_password(PWD)
        u.save()
    return u


def _profile(user, tipo, company=None):
    p, _ = UserProfile.objects.get_or_create(user=user)
    p.tipo_usuario = tipo
    p.company = company
    p.save()
    return p


class Command(BaseCommand):
    help = "Crea datos de demo (usuarios, empresas, productos, config, facturas)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Borra empresas/usuarios demo antes de crear.")

    def handle(self, *args, **opts):
        if opts["reset"]:
            self._reset()

        # --- Empresa A: electrostore -------------------------------------
        ana = _user("ana@demo.local", "Ana", "Torres")
        electro, _ = Company.objects.get_or_create(
            name="electrostore",
            defaults=dict(
                nit="900111111", company="ElectroStore SAS", phone="3001112233",
                email="electro@demo.local", direction="Cra 10 # 20-30",
                municipality="Bogota", creator_user=ana,
                url_logo=ContentFile(_PNG, name="electro.png"),
            ),
        )
        _profile(ana, TipoUsuario.CREATOR, electro)
        carlos = _user("carlos@demo.local", "Carlos", "Ruiz")
        _profile(carlos, TipoUsuario.WORKER, electro)
        dora = _user("dora@demo.local", "Dora", "Mesa")
        _profile(dora, TipoUsuario.ADMIN, electro)
        cliente = _user("cliente@demo.local", "Cami", "Solo")
        _profile(cliente, TipoUsuario.CLIENTE, None)

        t_elec = self._tipo(electro, ana, "Electronica")
        t_acc = self._tipo(electro, ana, "Accesorios")
        t_hog = self._tipo(electro, ana, "Hogar")

        productos = [
            ("Audifonos Bluetooth", t_elec, "80000", "50000", "5000", 20, True),
            ("Cargador USB-C",      t_acc,  "25000", "12000", "2000", 100, True),
            ("Teclado Mecanico",    t_elec, "180000", "120000", "10000", 5, True),
            ("Mouse Inalambrico",   t_acc,  "45000", "28000", "3000", 0, False),   # agotado
            ("Lampara LED",         t_hog,  "60000", "35000", "4000", 12, True),
            ("Power Bank 10000",    t_elec, "90000", "55000", "6000", 30, False),  # no publicado
        ]
        creados = {}
        for nombre, tipo, val, mayor, cf, stock, publicar in productos:
            p = self._producto(electro, ana, nombre, tipo, val, mayor, cf, stock, publicar)
            creados[nombre] = p

        Config_ProductModel.objects.get_or_create(
            tienda=electro,
            defaults=dict(
                creado_por=ana, costos_fijos=Decimal("3000000"),
                margen_ganancia=Decimal("1.5"), promedio_productos_vendidos=200,
            ),
        )

        # Facturas de electrostore (creadas por carlos)
        if not Factura.objects.filter(tienda=electro).exists():
            self._factura(electro, carlos, [(creados["Audifonos Bluetooth"], 2),
                                            (creados["Cargador USB-C"], 3)])
            self._factura(electro, carlos, [(creados["Lampara LED"], 1)])
            self._factura(electro, carlos, [(creados["Cargador USB-C"], 5),
                                            (creados["Teclado Mecanico"], 1)])

        # --- Empresa B: modatienda (para test de aislamiento) ------------
        beto = _user("beto@demo.local", "Beto", "Nino")
        moda, _ = Company.objects.get_or_create(
            name="modatienda",
            defaults=dict(
                nit="900222222", company="Moda Tienda", phone="3009998877",
                email="moda@demo.local", direction="Calle 5 # 6-7",
                municipality="Medellin", creator_user=beto,
                url_logo=ContentFile(_PNG, name="moda.png"),
            ),
        )
        _profile(beto, TipoUsuario.CREATOR, moda)
        t_ropa = self._tipo(moda, beto, "Ropa")
        self._producto(moda, beto, "Camiseta Basica", t_ropa, "40000", "22000", "2000", 50, True)
        self._producto(moda, beto, "Jean Slim", t_ropa, "120000", "70000", "6000", 15, True)

        self.stdout.write(self.style.SUCCESS(
            f"Demo OK. Empresas: {Company.objects.count()} | "
            f"Usuarios: {CustomUser.objects.count()} | "
            f"Productos: {ProductModel.objects.count()} | "
            f"Codigos de barras: {Bar_codeModel.objects.count()} | "
            f"Facturas: {Factura.objects.count()}"
        ))
        self.stdout.write("Logins demo: ana|carlos|dora|beto|cliente @demo.local / demo12345")

    # ------------------------------------------------------------------
    def _tipo(self, company, user, nombre):
        t, _ = TypeProductModel.objects.get_or_create(
            tienda=company, tipo_producto=nombre,
            defaults=dict(creado_por=user),
        )
        return t

    def _producto(self, company, user, nombre, tipo, val, mayor, cf, stock, publicar):
        p = ProductModel.objects.filter(tienda=company, nombre__iexact=nombre).first()
        if p:
            return p
        with transaction.atomic():
            p = ProductModel.objects.create(
                nombre=nombre, tipo_producto=tipo, detalles=f"{nombre} demo",
                valor=Decimal(val), valor_mayor=Decimal(mayor),
                valor_costos_fijos=Decimal(cf), unidades_disponibles=stock,
                disponible=stock > 0, publicar=publicar,
                tienda=company, creado_por=user,
            )
        return p

    def _factura(self, company, user, lineas):
        with transaction.atomic():
            factura = Factura.objects.create(subtotal=Decimal("0"), total=Decimal("0"), tienda=company, creado_por=user)
            total = Decimal("0")
            for producto, cant in lineas:
                sub = producto.valor * cant
                FacturaDetalle.objects.create(
                    factura=factura, producto=producto, cantidad=cant,
                    subtotal=sub, tienda=company, creado_por=user,
                )
                producto.unidades_disponibles -= cant
                if producto.unidades_disponibles == 0:
                    producto.disponible = False
                producto.save()
                total += sub
            factura.subtotal = total
            factura.total = total
            factura.save()
        return factura

    def _reset(self):
        emails = ["ana@demo.local", "carlos@demo.local", "dora@demo.local",
                  "beto@demo.local", "cliente@demo.local"]
        Company.objects.filter(name__in=["electrostore", "modatienda"]).delete()
        CustomUser.objects.filter(email__in=emails).delete()
        self.stdout.write("Datos demo borrados.")
