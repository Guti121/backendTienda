from rest_framework.throttling import AnonRateThrottle


class CatalogoAnonRateThrottle(AnonRateThrottle):
    """Throttle propio para los endpoints públicos de /catalogo/* (scope
    'catalogo', ver DEFAULT_THROTTLE_RATES).

    El catálogo web (Next.js) hace SSR: todas las visitas, de TODAS las
    tiendas, salen con la IP del servidor de catalog-web hacia este backend
    -> comparten un solo cubo del AnonRateThrottle global (60/min). Una sola
    ficha de producto ya dispara 3-4 requests (company, product,
    tipo-producto, relacionados); con tráfico real o un crawler indexando
    varios productos seguidos, 60/min se agota casi de inmediato (visto en
    producción: 429 en /catalogo/company, /catalogo/product,
    /catalogo/tipo-producto). Este scope, más generoso, es solo para estas
    cuatro vistas de solo lectura; el resto de la API (login, registro, etc.)
    sigue con el 'anon' de siempre.
    """
    scope = 'catalogo'
