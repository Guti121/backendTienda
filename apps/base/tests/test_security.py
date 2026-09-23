"""Pruebas de seguridad activas: fuerza bruta / bypass de throttle, JWT,
inyección SQL, CORS, fortaleza de contraseña, validación de archivos subidos.

Corren contra settings.test (DEBUG=False, como en producción en ese aspecto).
"""
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_company, make_user


class _CacheAisladaTestCase(TestCase):
    """Limpia el cache (LocMemCache) antes Y después de cada test: varios de
    estos agotan a propósito el AnonRateThrottle, y si no se limpia al salir
    esa cache es GLOBAL al proceso de test -> el resto de la suite (cualquier
    request anónima desde 127.0.0.1) hereda el throttle ya gastado."""
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()


class ThrottleYFuerzaBrutaTest(_CacheAisladaTestCase):
    def test_anon_throttle_corta_la_fuerza_bruta_en_login(self):
        c = APIClient()
        codes = [
            c.post("/login/", {"email": "nadie@test.com", "password": f"x{i}"}, format="json").status_code
            for i in range(65)
        ]
        self.assertGreater(codes.count(429), 0,
                           "el AnonRateThrottle (60/min) debería cortar antes de 65 intentos")

    def test_no_se_puede_evadir_el_throttle_falsificando_x_forwarded_for(self):
        # Simula lo que manda nginx de verdad: un valor previo (lo que haya
        # puesto el cliente) + la IP real, que nginx SIEMPRE agrega al final
        # (proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for). Con
        # NUM_PROXIES=1, DRF debe usar esa última IP, no la que "eligió" el
        # cliente -> todas las requests deben identificarse igual pese al
        # prefijo falso distinto en cada una.
        c = APIClient()
        codes = [
            c.post(
                "/login/", {"email": "nadie2@test.com", "password": f"x{i}"}, format="json",
                HTTP_X_FORWARDED_FOR=f"10.0.0.{i % 250}, 127.0.0.1",  # último = IP real (test client)
            ).status_code
            for i in range(65)
        ]
        self.assertGreater(codes.count(429), 0,
                           "con NUM_PROXIES=1 no debería poder evadirse variando el prefijo del XFF")

    def test_admin_login_no_tiene_rate_limit_propio(self):
        # Hecho conocido de Django (no introducido por este proyecto): el
        # login del admin no pasa por DRF ni por ningún throttle. Se deja
        # documentado como riesgo residual, no como algo a arreglar acá.
        c = APIClient()
        codes = [c.post("/admin/login/", {"username": "admin", "password": f"x{i}"}).status_code
                for i in range(20)]
        self.assertNotIn(429, codes)


class CatalogoThrottleTest(_CacheAisladaTestCase):
    """El scope 'catalogo' (600/min) es más generoso que 'anon' (60/min):
    el SSR de catalog-web comparte un solo cubo entre todas las tiendas y
    todas las visitas, y una sola ficha de producto ya son varios requests."""

    def test_mas_de_60_requests_no_se_cortan(self):
        company, _ = make_company(nombre="sectest5", email="sec5@test.com", nit="900995")
        c = APIClient()
        codes = [c.get(f"/catalogo/company/{company.name}").status_code for _ in range(65)]
        self.assertNotIn(429, codes, "el scope 'catalogo' no debería agotarse a los 60")

    def test_sigue_teniendo_un_tope(self):
        company, _ = make_company(nombre="sectest6", email="sec6@test.com", nit="900994")
        c = APIClient()
        codes = [c.get(f"/catalogo/company/{company.name}").status_code for _ in range(605)]
        self.assertGreater(codes.count(429), 0, "600/min debería cortar antes de 605 intentos")


class JWTTest(_CacheAisladaTestCase):
    def test_token_con_firma_rota_es_rechazado(self):
        make_company(nombre="sectest", email="sec@test.com", nit="900999")
        c = APIClient()
        r = c.post("/login/", {"email": "creador_sectest@test.com", "password": "pass12345"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        tampered = r.data["access"][:-4] + "AAAA"
        r2 = c.get("/store/retrieveCompany/", HTTP_AUTHORIZATION=f"Bearer {tampered}")
        self.assertEqual(r2.status_code, 401)

    def test_refresh_token_no_se_puede_reusar_tras_rotar(self):
        make_company(nombre="sectest2", email="sec2@test.com", nit="900998")
        c = APIClient()
        r = c.post("/login/", {"email": "creador_sectest2@test.com", "password": "pass12345"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        old_refresh = r.data["refresh"]
        self.assertEqual(c.post("/refresh-token/", {"refresh": old_refresh}, format="json").status_code, 200)
        # El primer refresh rota y blacklistea el token viejo (ROTATE_REFRESH_TOKENS +
        # BLACKLIST_AFTER_ROTATION en SIMPLE_JWT); reusarlo debe fallar.
        r_reuse = c.post("/refresh-token/", {"refresh": old_refresh}, format="json")
        self.assertEqual(r_reuse.status_code, 401)


class InyeccionYCorsTest(_CacheAisladaTestCase):
    def test_inyeccion_sql_en_busqueda_publica_no_hace_nada_raro(self):
        company, _ = make_company(nombre="sectest3", email="sec3@test.com", nit="900997")
        c = APIClient()
        payloads = ["' OR '1'='1", "'; DROP TABLE colletion_productmodel; --", "1' UNION SELECT NULL--"]
        for p in payloads:
            r = c.get(f"/catalogo/list/{company.name}?q={p}")
            self.assertEqual(r.status_code, 200)  # el ORM parametriza; ni error ni fuga

    def test_cors_no_refleja_un_origin_no_permitido(self):
        company, _ = make_company(nombre="sectest4", email="sec4@test.com", nit="900996")
        c = APIClient()
        r = c.get(f"/catalogo/list/{company.name}", HTTP_ORIGIN="https://evil-site.com")
        self.assertNotEqual(r.get("Access-Control-Allow-Origin"), "https://evil-site.com")


class RegistroSeguroTest(_CacheAisladaTestCase):
    def test_passwords_debiles_son_rechazadas(self):
        c = APIClient()
        for pw in ["1", "12345678", "password123", "qwertyuiop"]:
            r = c.post("/register/", {
                "username": f"weak_{pw}", "email": f"weak_{pw}@test.com",
                "password": pw, "password_verify": pw, "first_name": "a", "last_name": "b",
            }, format="json")
            self.assertEqual(r.status_code, 400, f"{pw!r} debería rechazarse")
            self.assertIn("password", r.data)

    def test_password_fuerte_se_acepta(self):
        c = APIClient()
        r = c.post("/register/", {
            "username": "strongpw", "email": "strongpw@test.com",
            "password": "Un-Password-Bastante-Largo-42", "password_verify": "Un-Password-Bastante-Largo-42",
            "first_name": "a", "last_name": "b",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def test_archivo_no_imagen_disfrazado_de_logo_es_rechazado(self):
        cliente = make_user("subearchivo", tipo=TipoUsuario.CLIENTE)
        malicious = SimpleUploadedFile("logo.png", b"<?php echo 'hola'; ?>", content_type="image/png")
        c = APIClient()
        c.force_authenticate(user=cliente)
        r = c.post("/store/createCompany/", {
            "nit": "777888", "company": "Malicioso", "name": "maltienda",
            "phone": "1", "email": "mal@test.com", "direction": "d", "municipality": "m",
            "url_logo": malicious,
        }, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("url_logo", r.data)
