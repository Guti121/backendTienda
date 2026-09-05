# Tienda Virtual — Análisis del proyecto y guía de optimización

> Documento generado el 2026-09-05 a partir de una revisión completa del código.
> Objetivo: entender cómo funciona todo el backend hoy y dejar un plan claro para
> optimizarlo (rendimiento, seguridad, correctitud, mantenibilidad y despliegue).

> **Repo canónico:** `C:\Users\mipc1\Documents\backendTienda\backendTienda`
> (remoto `github.com/Guti121/backendTienda.git`, rama `main`, último commit
> 2025-08-01, 46 commits). Es la versión vigente y sobre la que se trabaja.
>
> La copia en `C:\Users\mipc1\Documents\Proyecto Tienda\tienda\` es un snapshot
> antiguo del monorepo (backend + `Frontend_tienda`), congelado en 2025-04-26 (18
> commits, historia divergente). Le faltan features enteras: app `catalogo`,
> Celery + reportes de ventas (`inventario` vacío), signals, almacenamiento S3 e
> imágenes múltiples de producto. **Queda archivada; no se toca.**

---

## 1. Resumen ejecutivo

**Qué es:** API REST en Django + DRF para gestionar tiendas (multi-tenant por
`Company`). Cada tienda maneja su catálogo de productos, genera códigos de barras
EAN‑13, factura ventas descontando stock, y produce reportes de ventas diarios y
mensuales mediante tareas programadas de Celery. Existe además un catálogo público
(sin autenticación) por nombre de tienda y un flujo de onboarding de empleados por
código QR.

**Estado general:** funcional y con bastante lógica de negocio ya resuelta, pero
con deuda técnica acumulada: validaciones duplicadas en 3 capas, código muerto
(auth por Token legado), consultas N+1 en los listados, un bug de fecha congelada
en las tareas Celery, configuración de settings/Celery inconsistente entre
entornos, dependencias faltantes en `requirements.txt`, migraciones ignoradas por
git y ausencia casi total de tests.

**Prioridades recomendadas (detalle en §10):**
1. Corregir bugs que afectan datos: fecha congelada en tasks, condición de carrera
   al facturar, `apps.catalogo` fuera de `INSTALLED_APPS`.
2. Cerrar riesgos de seguridad: `fields = '__all__'`, `print()` de tokens, falta de
   throttling, secretos y `ALLOWED_HOSTS`.
3. Rendimiento: `select_related` / `prefetch_related` en listados, mover la
   generación de códigos de barras a Celery.
4. Unificar configuración (settings + Celery), arreglar `requirements.txt`,
   versionar migraciones.
5. Refactor: capa de servicios, quitar código muerto, tests.

---

## 2. Stack tecnológico

| Área | Tecnología |
|---|---|
| Framework | Django 5.1.7 |
| API | Django REST Framework 3.15.2 |
| Auth | `djangorestframework-simplejwt` 5.5.0 (JWT con rotación + blacklist) |
| Base de datos | MySQL (`mysqlclient` 2.2.7) |
| Tareas async | Celery 5.5.2 + Redis 5.2.1 (broker y result backend) |
| Scheduler | `django-celery-beat` 2.8.0 + `beat_schedule` estático en `celery.py` |
| Almacenamiento | AWS S3 vía `django-storages` + `boto3` (**faltan en requirements.txt**) |
| Imágenes | Pillow 11 |
| Códigos de barras | `python-barcode` (genera EAN‑13), `pyzbar` (lee, requiere zbar del SO) |
| QR | `qrcode` 8.0 |
| CORS | `django-cors-headers` 4.7.0 |
| Moneda/i18n | `babel` (formato COP) |

---

## 3. Arquitectura general

### Multi-tenant por `Company`
Casi todos los modelos de negocio heredan de `apps/myStore/models.py::BaseModel`,
que aporta:

```
tienda        -> FK a myStore.Company   (editable=False)
creado_por    -> FK a AUTH_USER_MODEL   (editable=False)
modificado_por-> FK a AUTH_USER_MODEL   (nullable)
creado_en / modificado_en -> timestamps automáticos
```

El aislamiento entre tiendas se logra **filtrando manualmente en cada
`get_queryset()`** con el helper `Tienda_Virtual/globalFunctions.py::company_owner(user)`,
que devuelve `user.profile.company`. No hay middleware ni manager que lo garantice:
si una vista olvida el filtro, se filtran datos de otras tiendas.

### Roles de usuario (`apps/base/models.py::TipoUsuario`)
- `cliente` — usuario recién registrado, sin tienda (valor por defecto).
- `creator` — creó la empresa; único que puede borrarla y configurar precios.
- `admin` — administrador dentro de una empresa.
- `worker` — empleado (puede facturar y leer códigos de barras).

Los permisos viven en `apps/base/api/user/viewsPermissions.py`
(`isCreator`, `isWorker`, `isAdmin`, `IsWorkerOrCreator`, `IsAdminOrCreator`).
Cada uno relee `request.user.profile.tipo_usuario`.

### Capas por app
```
apps/<app>/
  models.py
  admin.py
  signals.py            (colletion, shoppingcart)
  tasks.py              (inventario)
  api/
    urls.py
    views/ o views.py
    serializers/
```

---

## 4. Estructura de carpetas

```
Tienda_Virtual/
  settings/
    base.py          -> común (SIN config de DB, Celery ni S3)
    local.py         -> DEBUG=True, DB MySQL local, CORS hardcode
    production.py     -> HTTPS/HSTS, Celery, S3, ALLOWED_HOSTS desde env
    __init__.py       (vacío)
  urls.py            -> enруta todas las apps
  celery.py          -> instancia Celery + beat_schedule estático
  wsgi.py            -> usa settings.local y .env en /home/ubuntu/.env
  asgi.py
  globalFunctions.py -> company_owner(), profile_user()
apps/
  base/        -> CustomUser, UserProfile, JWT login/registro/logout, permisos
  myStore/     -> Company, Details_company, BaseModel, QR onboarding
  colletion/   -> ProductModel, TypeProductModel, ProductImage, Bar_codeModel, Config_ProductModel
  shoppingcart/-> Factura, FacturaDetalle, lectura de códigos de barras
  inventario/  -> ReporteVentasDiario/Mensual + tareas Celery + vistas de resumen
  catalogo/    -> catálogo PÚBLICO por nombre de tienda (NO está en INSTALLED_APPS)
manage.py      -> usa settings.local
requirements.txt
.env           -> solo DJANGO_SECRET_KEY + credenciales DB
```

Nota: `manage.py`, `wsgi.py`, `base.py`, `local.py` están listados en `.gitignore`
pero **ya están versionados** (aparecen como modificados en `git status`). Además
`*/migrations/*.py` está ignorado → las migraciones no se versionan.

---

## 5. Apps en detalle

### 5.1 `apps.base` — usuarios, autenticación y permisos

**Modelos**
- `CustomUser(AbstractUser)`: login por `email` (`USERNAME_FIELD = 'email'`),
  `first_name`/`last_name` obligatorios y capitalizados en `save()`.
- `UserProfile`: `OneToOne` con el usuario; `company` (FK nullable) + `tipo_usuario`.
  Se crea automáticamente como `cliente` en el registro.

**Endpoints** (montados en `Tienda_Virtual/urls.py` y `apps/base/api/urls.py`)

| Método | Ruta | Vista | Permiso |
|---|---|---|---|
| POST | `/login/` | `CustomTokenObtainPairView` | público |
| POST | `/refresh-token/` | `TokenRefreshView` | público |
| POST | `/logout/` | `LogoutView` (blacklist del refresh) | autenticado |
| POST | `/register/` | `RegisterUserView` | público |
| GET | `/base/listUsersCompany/` | `ListUserCompanyAPIView` | `IsAdminOrCreator` |
| PATCH | `/base/DestroyUsersCompany/<pk>/` | `UpdateUserCompanyAPIView` (expulsa: pone `cliente` + `company=None`) | `IsAdminOrCreator` |

**Login** (`CustomTokenObtainPairSerializer`): valida `email`/`password` con
`authenticate()`, exige que exista `profile`, y responde
`{ access, refresh, user: { email, username, typeUser } }`.

**Código muerto detectado:**
- `api/token/authentication.py::ExpiringTokenAuthentication` y
  `api/token/authentication_mixins.py::Authentication`: implementan expiración
  sobre el `TokenAuthentication` clásico de DRF. **Ya nadie los usa** (todo el
  proyecto usa `JWTAuthentication`). También sobra `TOKEN_EXPIRED_AFTER_SECONDS`
  en `base.py` y `rest_framework.authtoken` no está instalado.
- `authentication_mixins.py` hace `print(token)` → **fuga de credenciales en logs**.

### 5.2 `apps.myStore` — empresas y onboarding

**Modelos**
- `Company`: `nit` único, `name` único y validado (regex sin espacios), datos de
  contacto, `creator_user` (FK). `save()` hace `full_clean()` y borra el logo
  anterior en S3 si cambia.
- `Details_company`: datos fiscales (dv, actividad económica, etc.).
- `BaseModel` (abstracto, descrito en §3).

**Endpoints** (`/store/...`)

| Método | Ruta | Vista | Permiso |
|---|---|---|---|
| POST | `createCompany/` | `CompanyCreateAPIView` — exige `tipo_usuario=cliente` y sin empresa; al crear promueve a `creator` y vincula | autenticado |
| GET | `retrieveCompany/` | `CompanyRetrieveAPIView` (la del usuario) | `IsWorkerOrCreator` |
| PATCH | `updateCompany/` | `CompanyUpdateAPIView` (whitelist de campos) | `isCreator` |
| DELETE | `destroyCompany/` | `CompanyDestroyAPIView` — pone a todos los miembros como `cliente`, luego borra | `isCreator` |
| POST | `generar_qr/` | `GenerarQRView` — QR con `AccessToken` (5 min) que lleva `company`, `email`, `type_user` | `IsAdminOrCreator` |
| GET | `validar_qr/?token=` | `LeerQRView` — valida que el email del token sea el del usuario y lo afilia | autenticado |

**Problemas:**
- `api/permissions.py::IsCompanyMember.has_object_permission` compara
  `user.profile.company.id == obj.tienda` (id vs instancia) → **siempre False**.
  Actualmente no se usa, pero está listo para romper si alguien lo adopta.
- `qrCode.py`: múltiples `print(token)` (fuga). En `add_user_company`,
  `usuario_type == 1` / `== 2` compara contra `int`, pero `type_user` llega como
  string desde `request.data` → normalmente **no entra en ningún `if`**, el
  usuario queda con `company` asignada pero sigue como `cliente`.

### 5.3 `apps.colletion` — productos (núcleo del dominio)

> El nombre de la carpeta es `colletion` (falta de ortografía de "collection");
> conviene no renombrar sin plan de migración.

**Modelos**
- `TypeProductModel(BaseModel)`: categoría de producto (`tipo_producto`, `detalles`).
- `ProductModel(BaseModel)`: `nombre` (capitalizado), FK a tipo, `valor` (precio
  venta), `valor_mayor` (costo mayorista), `valor_costos_fijos`, `unidades_disponibles`,
  `disponible`, `numero_producto` (5 dígitos aleatorios únicos por tienda),
  `publicar` (visible en catálogo público).
  - `save()`: genera `numero_producto` y, dentro de `transaction.atomic()`, crea
    el `Bar_codeModel` (imagen PNG EAN‑13) **de forma síncrona**.
- `ProductImage(BaseModel)`: hasta 5 por producto, una `principal`; `clean()`
  valida. `upload_to` = `productos/<tienda>/<uuid>.<ext>`.
- `Bar_codeModel(BaseModel)`: `OneToOne` con producto, imagen del código + `code`
  EAN‑13 de 13 dígitos (`770` + `0123` + `numero_producto` + dígito de control).
- `Config_ProductModel(BaseModel)`: parámetros para el cálculo de precio sugerido
  (`costos_fijos` mensuales, `margen_ganancia`, `promedio_productos_vendidos`).

**Signals** (`signals.py`): al borrar `Bar_codeModel` o `ProductImage`, borra el
archivo en S3 (`post_delete`).

**Endpoints** (`/` raíz + resto bajo la misma app)

| Método | Ruta | Vista | Permiso | Notas |
|---|---|---|---|---|
| GET | `list/` | `ListProductAPIView` | `IsAdminOrCreator` | todos los productos de la tienda |
| GET | `listfilter/?q=` | `ProductListFilterAPIView` | `IsWorkerOrCreator` | solo disponibles, tope 10 |
| GET | `product/?q=&order=` | `ProductFilterAdminAPIView` | `IsAdminOrCreator` | filtros + orden 0–5, paginado |
| GET | `productDetail/<pk>/` | `ProductRetrieveAPIView` | `IsWorkerOrCreator` | serializer distinto para `creator` |
| POST | `create/` | `ProductCreateView` | `isCreator` | valida en la vista + serializer + modelo |
| PATCH | `updateProduct/<pk>/` | `ProductUpdateApiView` | `IsAdminOrCreator` | reemplaza imágenes |
| DELETE | `destroyproduct/<pk>/` | `ProductDestroyAPIView` | `IsAdminOrCreator` | borra imágenes en S3 |
| POST/DELETE/GET | `createtype/`, `destroytypeProduct/<pk>/`, `listType/`, `typeProductFilter/` | Type* | `IsAdminOrCreator` | |
| POST/DELETE/GET | `config/`, `config/destroy/`, `config/retrive/` | Config_Producto* | `isCreator` | 1 config por tienda |
| POST | `config/calculo/` | `PrecioSugeridoAPIView` | `IsAdminOrCreator` | precio = (valor_mayor + CF/u) · (1 + margen) |

**Problemas:**
- **Validación triplicada**: `ProductCreateView.create()` repite a mano lo que ya
  valida `ProductModelSerializer.validate()` y el propio `ProductModel.save()`.
- `ProductModelSerializer` usa `fields = '__all__'` → acepta `tienda`, `creado_por`,
  `disponible`, `publicar`, `numero_producto` desde el cliente (mass assignment).
- `PrecioSugeridoAPIView`: `isinstance(valor_mayor, int)` rechaza decimales y
  strings; frágil.
- `serializer_config.py::CreateParametrosSerializer`: los métodos `validate` y
  `create` están **anidados dentro de `class Meta`** (mal indentados) → nunca se
  ejecutan.
- N+1 en `ProductModelListFilterSerializer` / `ProductModelRetrieveProduct*`:
  `obj.imagenes.filter(principal=True)` y `instance.tipo_producto.tipo_producto`
  por fila, sin `prefetch_related`/`select_related`.
- Import basura `from calendar import c` en `view_product.py`.
- Generación de código de barras **síncrona** en cada alta de producto (I/O de
  imagen + escritura en S3).

### 5.4 `apps.shoppingcart` — facturación y lectura de códigos

**Modelos**
- `Factura(BaseModel)`: `fecha` (`auto_now_add`), `total`.
- `FacturaDetalle(BaseModel)`: FK a factura y a producto (`SET_NULL`),
  `nombre_producto` (copia histórica), `cantidad`, `valor_und`, `valor_mayor_und`,
  `valor_con_CF`, `subtotal`. `save()` recalcula varios campos desde el producto.

**Endpoints** (`/facturas/...`)

| Método | Ruta | Vista | Permiso |
|---|---|---|---|
| GET | `` | `FacturasListView` — filtro `month`/`year` o `date`; agrega totales y ganancia | `IsAdminOrCreator` |
| GET | `<pk>/` | `FacturasDetailView` | `IsWorkerOrCreator` |
| POST | `create/` | `FacturasCreateView` — verifica stock, descuenta unidades, crea factura+detalles | `IsWorkerOrCreator` |
| DELETE | `destroy/<pk>/` | `FacturaDestroyView` — **repone** stock y borra | `IsAdminOrCreator` |
| POST | `codigo_de_barras/` | `LecturaCodigoBarrasAPIView` — imagen → `pyzbar` → producto | `IsWorkerOrCreator` |
| POST | `codigo_de_barras_text/` | `LecturaCodigoBarrasTextAPIView` — código en texto | `IsWorkerOrCreator` |
| GET | `api/barcode/<pk>/` | `RetrieveBarCode` | autenticado |

**Flujo de venta** (`FacturasCreateView.perform_create` + `FacturaCreateSerializer.create`):
1. Agrupa cantidades por producto (`defaultdict`).
2. Verifica stock de todos; si falta, `ValidationError`.
3. Descuenta unidades y marca `disponible=False` si llega a 0.
4. Crea `Factura` (total 0), luego cada `FacturaDetalle` con `subtotal = valor · cantidad`,
   acumula y guarda el `total`.

**Problemas:**
- **Condición de carrera / sobreventa**: la comprobación y el descuento de stock no
  usan `select_for_update()` ni transacción; dos ventas simultáneas del mismo
  producto pueden dejar stock negativo.
- `FacturasCreateView.post` captura `serializers.ValidationError` y responde **404**
  (debería ser 400).
- Lógica de importes dividida entre `FacturaCreateSerializer.create` (subtotal) y
  `FacturaDetalle.save()` (`valor_mayor_und`, `valor_con_CF`, `valor_und`).
- `FacturasListView.list` recorre el queryset en Python (`for factura in queryset`)
  además de un `aggregate` — doble trabajo — y hay ~10 `print()` de depuración.
- `LecturaCodigoBarrasAPIView` devuelve `204 NO CONTENT` con body cuando no
  encuentra el código (semántica incorrecta).

### 5.5 `apps.inventario` — reportes de ventas

**Modelos**: `ReporteVentasDiario` y `ReporteVentasMensual` (por `tienda` + `fecha`,
con totales de productos, valor mayorista, CF y subtotal).

**Tareas Celery** (`tasks.py`)
- `generar_reporte_ventas_dia` — beat: todos los días 23:59. Recorre `Company`,
  agrega `FacturaDetalle` del día, crea/actualiza el reporte diario.
- `generar_reporte_ventas_mes` — beat: día 1 a las 03:00. Suma los diarios del mes
  anterior en el mensual.
- `generar_reporte_ventas_dia_update` / `generar_reporte_ventas_mes_update` — se
  disparan por signal cuando se borra un `FacturaDetalle` (`shoppingcart/signals.py`),
  para recomputar el reporte de esa fecha si ya existía.

**Endpoints** (`/inventario/...`, todos `isCreator`)

| Método | Ruta | Vista |
|---|---|---|
| GET | `` | `InventarioView` — reportes diarios, filtro `month`/`year` |
| GET | `mensual/` | `InventarioMesView` — reportes mensuales |
| GET | `resumen/` | `ResumenVentasMensualView` — agrega diarios de un mes |
| POST | `productos/` | `InventarioProductos` — valor de inventario actual (unidades·precio) |

**Problemas:**
- **Bug de fecha congelada**: `now_local = localtime(timezone.now())` se calcula
  **al importar el módulo**, y todas las tareas usan `now_local.date()`. El worker
  de Celery, que vive días, generará reportes con la fecha del arranque del worker.
  Debe calcularse dentro de cada tarea.
- `Sum('cantidad') or 0` dentro de `aggregate(...)` no hace lo que parece: el `or 0`
  se evalúa sobre el objeto `Sum` (siempre truthy), no sobre el resultado. El
  `or 0` real está luego en `reporte['x'] or 0`, así que "funciona" por accidente.
- `ReporteVentasMensualSerializer` apunta a `model = ReporteVentasDiario`
  (copiar‑pegar); hoy los campos coinciden pero es una trampa.
- `InventarioProductos` usa `POST` para una consulta de solo lectura.
- Nombre de archivo `api/inventrio_views.py` (typo).

### 5.6 `apps.catalogo` — catálogo público

Vistas **sin autenticación** (`authentication_classes = []`) que exponen, por
nombre de tienda, los productos con `disponible=True` y `publicar=True`.

**Endpoints** (`/catalogo/...`)

| Método | Ruta | Vista |
|---|---|---|
| GET | `list/<name>?tipo=&orden=&fecha=` | `CatalogoListView` |
| GET | `product/<name>/<id>` | `CatalogoProductRetrieveView` |
| GET | `tipo-producto/<name>` | `CatalogoTipoProductListView` |
| GET | `company/<name>` | `CompanyDetailView` |

**Problema crítico:** `apps.catalogo` **no está en `LOCAL_APPS`/`INSTALLED_APPS`**.
Funciona solo porque no define modelos propios ni migraciones y sus URLs se
incluyen a mano. Consecuencias: no aparece en el admin, `manage.py check` no la
inspecciona, señales/`AppConfig.ready()` no se ejecutarían, y `makemigrations` la
ignora. Hay que añadirla a `LOCAL_APPS`.

Rutas sin `/` final (`list/<str:name>` en vez de `list/<str:name>/`) — inconsistente
con el resto del proyecto.

---

## 6. Autenticación y permisos (resumen)

- **JWT** (`SIMPLE_JWT`): access 15 min, refresh 1 día, rotación + blacklist.
  `TOKEN_BLACKLIST_MODEL` está fijado a `token_blacklist.OutstandingToken`, lo cual
  es incorrecto (el modelo de blacklist es `BlacklistedToken`); mejor quitar esa
  clave y dejar el valor por defecto.
- `REST_FRAMEWORK` define `DEFAULT_AUTHENTICATION_CLASSES = (JWTAuthentication,)`
  pero **no** `DEFAULT_PERMISSION_CLASSES`. Cualquier vista que olvide
  `permission_classes` queda abierta (`AllowAny`). Conviene poner
  `DEFAULT_PERMISSION_CLASSES = ['rest_framework.permissions.IsAuthenticated']`.
- No hay **throttling** en ninguna vista (login y registro incluidos).
- Los 5 permisos custom repiten el patrón `getattr(request.user, 'profile', None)`
  + comparación de string. Se pueden reducir a una clase parametrizada por roles.

---

## 7. Configuración y despliegue

| Aspecto | Situación actual | Riesgo |
|---|---|---|
| `manage.py` | `settings.local` | ok en dev |
| `wsgi.py` | `settings.local` + `.env` en `/home/ubuntu/.env` | en el servidor corre con settings de **desarrollo** (DEBUG configurable, sin HTTPS/HSTS ni S3 forzado) |
| `celery.py` | `settings.production` fijo | usa un settings distinto al de la web; si `production.py` peta por env faltante, Celery no arranca |
| Config Celery | solo en `production.py` (`CELERY_BROKER_URL`, etc.) | ejecutar Celery con `local`/`base` = sin broker configurado |
| `beat_schedule` | dict estático en `celery.py` **y** `django_celery_beat` instalado | doble fuente de verdad para tareas programadas |
| `production.py` | lee `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`, claves AWS de env; `.split(',')` sin guardas | si falta una var → `AttributeError: 'NoneType'` al arrancar |
| `.env` | solo `DJANGO_SECRET_KEY` + credenciales DB | faltan las vars que `production.py` espera |
| `requirements.txt` | **faltan `django-storages` y `boto3`** (usados en `production.py`) | `pip install -r` no deja el proyecto listo para prod |
| `requirements.txt` | sin separar dev/prod, sin `boto3`, sin `gunicorn`/`uwsgi` | despliegue manual y frágil |
| Migraciones | `*/migrations/*.py` en `.gitignore`; `git status` muestra muchas borradas | cada entorno genera sus propias migraciones → divergencia de esquema |
| Bucket S3 | `AWS_STORAGE_BUCKET_NAME = 'media-stockapp03042025'` hardcodeado | debería venir de env |
| `TIME_ZONE` | `America/Bogota`, `USE_TZ=True` | ok; pero `LANGUAGE_CODE='en-us'` |
| Archivos sueltos | `8000`, `barcodes/`, `productos/`, `profileCompany/` en la raíz | artefactos locales; limpiar y confirmar `.gitignore` |

---

## 8. Mapa de endpoints (índice rápido)

```
POST   /login/                          JWT (email + password)
POST   /refresh-token/
POST   /logout/                         blacklist refresh
POST   /register/

GET    /list/                           productos (admin/creator)
GET    /listfilter/?q=                  productos disponibles (worker/creator)
GET    /product/?q=&order=              productos con filtros + orden
GET    /productDetail/<pk>/
POST   /create/                         crear producto
PATCH  /updateProduct/<pk>/
DELETE /destroyproduct/<pk>/
POST   /createtype/  GET /listType/  GET /typeProductFilter/  DELETE /destroytypeProduct/<pk>/
POST   /config/  GET /config/retrive/  DELETE /config/destroy/  POST /config/calculo/

GET    /facturas/                       lista + totales
GET    /facturas/<pk>/
POST   /facturas/create/
DELETE /facturas/destroy/<pk>/
POST   /facturas/codigo_de_barras/      (imagen)
POST   /facturas/codigo_de_barras_text/ (texto)
GET    /facturas/api/barcode/<pk>/

GET    /inventario/                     reportes diarios
GET    /inventario/mensual/             reportes mensuales
GET    /inventario/resumen/             agregado del mes
POST   /inventario/productos/           valor de inventario actual

GET    /base/listUsersCompany/
PATCH  /base/DestroyUsersCompany/<pk>/

POST   /store/createCompany/
GET    /store/retrieveCompany/
PATCH  /store/updateCompany/
DELETE /store/destroyCompany/
POST   /store/generar_qr/
GET    /store/validar_qr/?token=

GET    /catalogo/list/<name>            (público)
GET    /catalogo/product/<name>/<id>    (público)
GET    /catalogo/tipo-producto/<name>   (público)
GET    /catalogo/company/<name>         (público)
```

---

## 9. Flujos de negocio principales

1. **Registro → empresa**: `POST /register/` crea `CustomUser` + `UserProfile(cliente)`.
   `POST /store/createCompany/` exige `cliente` sin empresa; crea `Company`,
   promueve a `creator` y vincula.
2. **Alta de empleados por QR**: `creator`/`admin` llama `generar_qr/` con
   `email` + `type_user`; se genera un `AccessToken` de 5 min embebido en el QR.
   El empleado, autenticado, llama `validar_qr/?token=`; si su email coincide, se
   afilia a la empresa. (Ver bug de `type_user` en §5.2.)
3. **Catálogo**: `creator` crea `TypeProductModel` y `ProductModel`. Al guardar el
   producto se genera `numero_producto` y su `Bar_codeModel` (EAN‑13) en S3.
   `publicar=True` lo expone en `/catalogo/`.
4. **Venta**: `worker`/`creator` `POST /facturas/create/` con `detalles`
   (`producto`, `cantidad`). Se valida stock, se descuenta, se crea `Factura` +
   `FacturaDetalle`. Borrar la factura repone el stock.
5. **Reportes**: Celery beat genera `ReporteVentasDiario` cada noche y
   `ReporteVentasMensual` el día 1. Borrar un `FacturaDetalle` dispara un signal
   que recomputa el reporte de esa fecha.
6. **Precio sugerido**: con `Config_ProductModel` (costos fijos, margen, unidades
   proyectadas), `POST /config/calculo/` devuelve
   `precio = (valor_mayor + costos_fijos/unidades) · (1 + margen)`.

---

## 10. Diagnóstico y plan de optimización

### Fase 0 — Bugs que corrompen datos o rompen entornos (hacer ya)

> **Estado (2026-09-05):** 0.1–0.6 y 0.8 aplicados en el working tree (sin
> commitear todavía, por decisión del autor) y **verificados con una suite de 13
> tests** que pasa en verde:
>
> - Se montó un settings de prueba con SQLite en memoria
>   (`Tienda_Virtual/settings/scratch_sqlite.py`, temporal) porque el `.env` local
>   apunta a un MySQL sin acceso en esta máquina.
> - `migrate` sobre una BD nueva aplica **todo el set de migraciones del working
>   tree sin errores** → el `0001_initial` "squasheado" + `colletion/0002` son
>   internamente consistentes con los modelos (dato clave para 0.7).
> - Tests cubren: `_hoy_local()` dinámico (0.1); `apps.catalogo` instalada (0.2);
>   venta descuenta stock / stock exacto marca `disponible=False` / **sobreventa
>   devuelve 400 con rollback** / carrito vacío 400 / líneas repetidas se agrupan
>   (0.3, 0.4); `CreateParametrosSerializer.validate` ahora se ejecuta (0.5);
>   `GenerarQRView` rechaza `type_user` no numérico y acepta `"1"`, y
>   `add_user_company` mapea `"1"→worker` / `"99"→False` (0.8).
> - El settings y el archivo de tests de prueba **no se dejaron en el repo**
>   (están guardados en el scratchpad de la sesión); se incorporarán como suite
>   real en el paso de testing (Fase 5) con un `settings/test.py` propio.
>
> **0.7 queda pendiente** y cambia de enfoque (ver nota abajo).

| # | Problema | Archivo | Acción | Estado |
|---|---|---|---|---|
| 0.1 | Fecha congelada en tareas Celery | `apps/inventario/tasks.py` | `now_local` de módulo → helper `_hoy_local()` llamado dentro de cada `@shared_task`. | ✅ hecho |
| 0.2 | `apps.catalogo` fuera de `INSTALLED_APPS` | `settings/base.py` | Añadido `'apps.catalogo'` a `LOCAL_APPS`. `manage.py check` OK, sin migraciones nuevas. | ✅ hecho |
| 0.3 | Sobreventa por carrera al facturar | `shoppingcart/api/views.py` | `perform_create` ahora corre en `transaction.atomic()` con `select_for_update()` sobre los productos; descuento con `bulk_update`. | ✅ hecho |
| 0.4 | `ValidationError`/`ValueError` → HTTP 404 al facturar | `shoppingcart/api/views.py::FacturasCreateView.post` | Ambos `except` devuelven `400`. | ✅ hecho |
| 0.5 | `CreateParametrosSerializer.validate/create` dentro de `Meta` | `colletion/api/serializers/serializer_config.py` | `validate` movido al serializer y ahora hace `return data`; `create` redundante eliminado (era el de `ModelSerializer`). | ✅ hecho |
| 0.6 | `django-storages` y `boto3` ausentes | `requirements.txt` | Añadidos `django-storages==1.14.6` (ya en el venv) y `boto3>=1.34,<2.0`. **Falta `pip install boto3` en el venv.** | ✅ hecho (pendiente instalar) |
| 0.7 | Migraciones ignoradas por git + set local a medias | `.gitignore`, `apps/*/migrations/` | Ver nota. **La BD local tiene datos → NO regenerar de cero.** | ⏳ pendiente |
| 0.8 | `type_user` string vs int en QR | `myStore/api/qrCode.py` | `GenerarQRView` valida `int(type_user) in (1,2)` antes de emitir el QR; `add_user_company` parsea con `int()` y mapea `{1:'worker',2:'admin'}`, devolviendo `False` si es inválido. Se quitaron 2 `print(token)`. | ✅ hecho |

**Nota 0.7 (enfoque corregido).** Como la BD local ya tiene datos aplicados, no
se puede hacer `makemigrations` desde cero. El camino seguro:
1. Restaurar las migraciones borradas que sí están en `HEAD`
   (`git checkout -- apps/*/migrations/`), para no perder historia ya aplicada.
2. Añadir la nueva `apps/colletion/migrations/0002_alter_productimage_imagen.py`
   (hoy *untracked*) al repo.
3. Editar `.gitignore`: quitar `*/migrations/*.py` (dejar solo la exclusión de
   `__pycache__`) para que las migraciones se versionen a partir de ahora.
4. `python manage.py migrate --plan` en la máquina del autor para confirmar que el
   estado de la BD y el árbol de migraciones coinciden.
Esto se hará en una sesión aparte con acceso a la BD real; por ahora el working
tree se deja como está.

### Fase 1 — Seguridad

> **Estado (2026-09-05):** aplicada en el working tree y verificada con la suite
> (ahora 18 tests, todo en verde bajo el settings SQLite temporal). `manage.py
> check` OK con `local`; con `production` ahora **falla al arrancar con un mensaje
> claro** si falta una variable de entorno (antes: `AttributeError: NoneType`).

- ✅ **`fields = '__all__'` eliminado** en:
  - `ProductModelSerializer` → lista explícita; `id`, `numero_producto`,
    `disponible` como `read_only_fields` (el cliente ya no puede fijarlos).
  - `TypeProductModelSerializer` → `['id', 'tipo_producto', 'detalles']`.
  - `CreateParametrosSerializer` / `ListarParametrosSerializer` → campos de negocio
    explícitos; `disponible` `read_only`.
  - `CreateCompanySerializer` → campos explícitos; `creator_user` `read_only` y la
    vista `CompanyCreateAPIView` ahora hace `serializer.save(creator_user=user)`.
- ✅ **`print()` fuera del código de request/tareas**: los de `qrCode.py`
  (incluido el que volcaba token + email), `shoppingcart/api/views.py`,
  `colletion/api/views/*`, `colletion/models.py`, `shoppingcart/signals.py` y
  `inventario/tasks.py` → sustituidos por `logging` (`logger.info/warning/exception`).
  Se añadió un `LOGGING` con handler de consola en `settings/base.py`.
- ✅ **`DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`** + `AnonRateThrottle`
  (`anon: 60/min`) en `REST_FRAMEWORK`. Se añadió `permission_classes = [AllowAny]`
  a `RegisterUserView` y `LogoutView` para que sigan siendo públicos; el catálogo
  ya usaba `permission_classes = []`.
- ✅ **`production.py`**: helpers `_required()` / `_csv()` que fallan con
  `ImproperlyConfigured` y mensaje claro; `AWS_STORAGE_BUCKET_NAME` y
  `SECRET_KEY` ahora vienen de env (sin hardcode).
- ✅ **`SIMPLE_JWT['TOKEN_BLACKLIST_MODEL']` eliminado** (apuntaba al modelo
  equivocado; el default ya funciona con `token_blacklist` instalado).
- ✅ **Código muerto de auth por Token borrado**: `authentication.py`,
  `authentication_mixins.py`, `TOKEN_EXPIRED_AFTER_SECONDS`, y los imports
  huérfanos (`from ...authentication_mixins import Authentication` en dos vistas,
  `TokenAuthentication` en `codebar.py`, `authtoken.views` en `token/views.py`).
- ✅ **`LANGUAGE_CODE`** `'en-us'` → `'es-co'` (con `USE_I18N=True` los mensajes de
  error de DRF salen en español donde hay traducción).
- ⏳ **`wsgi.py`**: sigue apuntando a `settings.local`. El autor **no va a desplegar
  P1** por ahora, así que se deja; cuando se retome, cambiar a `production` y
  parametrizar la ruta del `.env`.

**Aviso de compatibilidad con el frontend:** al recortar los serializers, las
respuestas de listado/creación ya **no incluyen** campos como `tienda`,
`creado_por`, `modificado_por`, `creado_en`, `modificado_en` (en
`TypeProductModelSerializer` y config) ni aceptan del body `numero_producto` /
`disponible` / `creator_user`. Si el cliente móvil dependía de alguno, habrá que
ajustarlo o volver a exponerlo como `read_only`.

### Fase 2 — Rendimiento

> **Estado (2026-09-05):** parte de código aplicada y verificada (suite de 22
> tests, todo verde). Índices y código-de-barras→Celery **diferidos**
> deliberadamente (ver más abajo).

- ✅ **N+1 en listados eliminado**:
  - `view_product.py`: helper `_productos_de(company)` con
    `.select_related('tipo_producto').prefetch_related('imagenes').order_by('id')`,
    usado por `ListProductAPIView`, `ProductRetrieveAPIView`,
    `ProductFilterAdminAPIView` y `ProductListFilterAPIView`.
  - `catalogo/api/views/views.py`: `select_related`/`prefetch_related` en
    `CatalogoListView` y `CatalogoProductRetrieveView`.
  - `shoppingcart`: `FacturasDetailView` con
    `select_related('creado_por','tienda').prefetch_related('detalles__producto')`.
  - **Serializers**: `get_imagen_principal` / `get_image_principal` ya no hacen
    `obj.imagenes.filter(principal=True)` (rompía el prefetch, 1 query por fila);
    ahora recorren `obj.imagenes.all()` en Python. Test: nº de queries constante
    con 2 vs 6 productos.
- ✅ **`FacturasListView.list`**: se eliminó el `aggregate` con triple JOIN a
  `producto` (calculaba `total_x_mayor` / ganancias que **nadie usaba** — el
  bloque de respuesta estaba comentado) y el helper `total_facturas()`. Ahora:
  `Count('id')` + `Sum('total')` sin JOIN (para no inflar el total) y un
  `Sum('detalles__cantidad')` aparte. Test: los totales no se inflan.
- ✅ **Búsqueda por `valor`**: `Q(valor__icontains=query)` sobre `Decimal`
  (casteaba toda la columna) → helper `_busqueda_producto_q()` que solo compara
  `Q(valor=Decimal(query))` si `query` parsea como número; texto basura ya no
  puede tumbar la query.
- ✅ **`company_owner(user)` / `profile_user(user)`** (`globalFunctions.py`):
  usan el accesor `user.profile` (cacheado en la instancia por Django) en vez de
  un `get_object_or_404(UserProfile, ...)` nuevo en cada llamada. 3 llamadas por
  request pasan de ~6 queries a 2. Se conserva el `Http404` si no hay perfil.
- ⏳ **Índices** (`db_index` / `Meta.indexes` en `ProductModel(tienda,nombre)`,
  `numero_producto`, `Bar_codeModel.code`, `ReporteVentasDiario(tienda,fecha)`,
  `FacturaDetalle.factura`): **diferido a la sesión de migraciones** (junto con
  0.7), que es cuando se correrá `migrate` contra la BD real.
- ⏳ **Código de barras a Celery**: **diferido a Fase 3**, en bloque con la
  unificación de la config de Celery + `CELERY_TASK_ALWAYS_EAGER` en local +
  comando `backfill_barcodes`. Hacerlo antes obliga a configurar Celery a medias.

### Fase 3 — Configuración unificada

> **Estado (2026-09-05):** núcleo aplicado y verificado (suite de 28 tests en
> verde, `manage.py check` OK, `manage.py backfill_barcodes --help` OK).

- ✅ **Config de Celery en `base.py`** (broker/backend por env con default Redis
  local, serializers, `CELERY_TIMEZONE = TIME_ZONE`, `CELERY_TASK_ALWAYS_EAGER`
  por env, `CELERY_TASK_EAGER_PROPAGATES`). Se quitó el bloque duplicado de
  `production.py`. Ahora `celery -A Tienda_Virtual worker` funciona con cualquier
  módulo de settings.
- ✅ **`celery.py`**: deja de clavar `DJANGO_SETTINGS_MODULE` a `production` →
  `local` (consistente con `manage.py`/`wsgi.py`; en prod se exporta la env var).
- ✅ **`settings/local.py`** (no versionado): `CELERY_TASK_ALWAYS_EAGER = True`
  → las tareas corren en el acto, sin Redis ni worker, en desarrollo. Un clon
  nuevo lo obtiene poniendo `CELERY_TASK_ALWAYS_EAGER=True` en su `.env`.
- ✅ **Beat schedule**: fuente única = el dict en `celery.py` (versionado).
  `django_celery_beat` queda instalado pero sin usar (quitarlo toca la BD → se
  hace en la sesión de migraciones).
- ✅ **Código de barras asíncrono**: `ProductModel.save()` ya no renderiza el PNG
  ni lo sube en la request; encola `apps/colletion/tasks.py::generar_codigo_barras_task`
  vía `transaction.on_commit` (idempotente, tolera producto borrado, 3 reintentos).
  El método `generarcodigo_barras(numero, tienda, creado_por)` pasó a
  `crear_codigo_barras()` que lee de `self`.
- ✅ **Comando `manage.py backfill_barcodes [--sync] [--dry-run]`** para los
  productos que quedaron sin código.
- ✅ **`.env.example`** con todas las claves que leen los settings.
- ⏳ **S3 a `base.py`** con toggle (`USE_S3`): **diferido**. `production.py`
  funciona y moverlo ahora no aporta nada en dev; se hará junto con el split de
  requirements.
- ⏳ **`requirements/` dividido** (`base` / `local` / `production` + `gunicorn`):
  diferido (P1 no se despliega; un solo `requirements.txt` basta por ahora).
- ⏳ **Quitar `django_celery_beat`** de `INSTALLED_APPS`: diferido a la sesión de
  migraciones (drop de ~15 tablas en una BD con datos).

### Fase 4 — Arquitectura y mantenibilidad

> **Estado (2026-09-05):** subconjunto de bajo riesgo aplicado y verificado
> (suite de 35 tests en verde, `manage.py check` OK). Lo estructural grande
> (capa de servicios, renombrados) queda diferido con motivo.

- ✅ **5 permisos → `RolePermission`**: `viewsPermissions.py` ahora tiene una
  clase base `RolePermission` con `allowed_roles`; `isCreator`/`isWorker`/
  `isAdmin`/`IsWorkerOrCreator`/`IsAdminOrCreator` son solo la lista de roles.
  Los nombres se conservan → ningún import de las vistas se rompe. Comportamiento
  idéntico (auth + activo + rol), verificado con tests.
- ✅ **Validación de producto unificada en el serializer**:
  `ProductCreateView.create()` tenía ~65 líneas de `float()` + `try/except` que
  duplicaban `ProductModelSerializer.validate()` y `ProductModel.save()`. Ahora
  toda la validación (requeridos, `valor > 0`, `valor_mayor > 0`,
  `valor >= valor_mayor`, `unidades > 0`, nombre no duplicado por tienda
  case-insensitive) vive en `validate()`. La vista queda solo con
  `perform_create` (asigna `tienda`/`creado_por`). Los errores ahora son por
  campo (`{"valor": [...]}`) en vez de `{"error": "..."}` — **posible ajuste en
  el frontend**.
- ✅ **`BaseModel.save()` eliminado**: dependía de un atributo `request_user` que
  no se asignaba en ningún lado (código muerto), y además tenía un bug latente
  (`if not self.tienda` revienta si `tienda_id` es None). El patrón real
  (`serializer.save(tienda=..., creado_por=...)`) no lo necesitaba.
- ✅ **Imports basura eliminados**: `from venv import create`
  (`viewsUserCreateType.py`), `from email.mime import image` / `from typing import
  Required` / `import time` (`serializer.py`), `from logging import
  raiseExceptions` / `import string` / `from urllib import request`
  (`view_config_price.py`), `import string` / `from tokenize import String`
  (`qrCode.py`). (`from calendar import c` ya se quitó en Fase 2.)
- ⏳ **Capa de servicios** (`apps/<app>/services.py`): **diferido**. Es un
  refactor grande y merece su propio esfuerzo; la consolidación de permisos y
  validación ya reduce buena parte del desorden.
- ⏳ **Renombrados** (`colletion→collection`, `myStore→mystore`,
  `inventrio_views.py`): diferido a una sesión dedicada (tocan app labels,
  imports en todo el repo y migraciones).
- ⏳ **Router/`ModelViewSet`** y unificar `trailing slash` en catálogo: diferido
  (cambia URLs públicas; poco urgente).

### Fase 5 — Calidad y observabilidad

- **Tests**: hoy todos los `tests.py` están vacíos. Empezar por los flujos de
  dinero/stock:
  - facturar descuenta stock y bloquea sobreventa (incluida la concurrencia);
  - borrar factura repone stock;
  - tareas de reporte diario/mensual con fechas controladas (`freezegun`);
  - aislamiento multi-tenant (un `creator` no ve datos de otra tienda);
  - permisos por rol en cada endpoint.
- `pytest` + `pytest-django` + `factory_boy` + `coverage`.
- **Documentación de API**: `drf-spectacular` (OpenAPI/Swagger) — hoy no hay.
- `logging` estructurado (JSON) y captura de errores (Sentry) en lugar de `print`.
- CI (GitHub Actions): `ruff`/`flake8`, `black`, `python manage.py check --deploy`,
  `makemigrations --check`, `pytest`.
- `django-environ` para tipado y validación de variables de entorno.
- Añadir `python manage.py check --deploy` a la rutina de release
  (avisará de `DEBUG`, cookies, HSTS, `SECRET_KEY`, etc.).

---

## 11. Checklist accionable

- [x] 0.1 Fecha dentro de las tareas Celery
- [x] 0.2 `apps.catalogo` en `INSTALLED_APPS`
- [x] 0.3 `select_for_update` + `atomic` al facturar
- [x] 0.4 Código HTTP correcto en errores de facturación
- [x] 0.5 Arreglar `CreateParametrosSerializer`
- [x] 0.6 `boto3` + `django-storages` en requirements *(falta `pip install boto3`)*
- [ ] 0.7 Versionar migraciones *(pendiente; requiere acceso a la BD real)*
- [x] 0.8 Normalizar `type_user` del QR
- [x] 1.x Quitar `fields='__all__'`, `print()`, añadir throttling y permisos por defecto
- [x] 1.x Borrar auth por Token legado
- [x] 1.x `production.py` con guardas de env; `TOKEN_BLACKLIST_MODEL` eliminado; `LANGUAGE_CODE=es-co`
- [ ] 1.x `wsgi.py` → `settings.production` (diferido: P1 no se despliega)
- [x] 2.x `select_related`/`prefetch_related` en listados + serializers (N+1 fuera)
- [x] 2.x Totales de facturas sin JOIN triple; `company_owner` cacheado; búsqueda `valor` sin cast
- [ ] 2.x Índices de BD *(diferido: sesión de migraciones)*
- [ ] 2.x Código de barras en Celery *(diferido: Fase 3)*
- [x] 3.x Config Celery en `base.py` + `CELERY_TASK_ALWAYS_EAGER` + `.env.example`
- [x] 3.x Código de barras → Celery (`transaction.on_commit`) + `backfill_barcodes`
- [ ] 3.x S3 a `base.py` con toggle + split de `requirements/` *(diferido)*
- [ ] 3.x Quitar `django_celery_beat` *(diferido: sesión de migraciones)*
- [x] 4.x Permisos unificados (`RolePermission`) + validación de producto única en el serializer + `BaseModel.save()` muerto fuera + imports basura
- [ ] 4.x Capa de servicios (`services.py`) *(diferido)*
- [ ] 4.x Renombrar apps/archivos con typos *(diferido: sesión de migraciones)*
- [ ] 5.x Tests de stock/reportes/multi-tenant + OpenAPI + CI

---

## 12. Referencia rápida de archivos clave

| Necesito tocar... | Archivo |
|---|---|
| Login / JWT | `apps/base/api/token/` |
| Roles y permisos | `apps/base/api/user/viewsPermissions.py` |
| Campos comunes (tienda/creado_por) | `apps/myStore/models.py::BaseModel` |
| Aislamiento por tienda | `Tienda_Virtual/globalFunctions.py` |
| Producto + código de barras | `apps/colletion/models.py` |
| Alta/edición de producto | `apps/colletion/api/views/view_product.py` |
| Cálculo de precio | `apps/colletion/api/views/view_config_price.py` |
| Facturación y stock | `apps/shoppingcart/api/views.py` + `serializers/serializers.py` |
| Lectura de códigos de barras | `apps/shoppingcart/api/codebar.py` |
| Reportes / tareas Celery | `apps/inventario/tasks.py` + `Tienda_Virtual/celery.py` |
| Recompute de reporte al borrar venta | `apps/shoppingcart/signals.py` |
| Catálogo público | `apps/catalogo/api/` |
| Empresas / QR onboarding | `apps/myStore/api/` |
| Settings por entorno | `Tienda_Virtual/settings/` |
```
