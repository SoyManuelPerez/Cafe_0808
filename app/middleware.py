"""Cabeceras de seguridad, protección CSRF y límite de peticiones por IP."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import API_REQ_POR_MINUTO, COOKIE_SECURE
from app.security import LimiteVentana, ip_cliente

_limite_api = LimiteVentana(API_REQ_POR_MINUTO, 60)
_METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}

# Landing: sin scripts en línea. Fuentes de Google.
CSP_LANDING = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
)
# Sistema: los botones usan onclick="..." (por eso 'unsafe-inline' en scripts),
# pero solo se cargan scripts de este dominio y de cdnjs (Excel).
CSP_SISTEMA = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "object-src 'self' blob:; frame-src 'self' blob:; "
    "worker-src 'self'; manifest-src 'self'; "
    # Sin frame-ancestors aquí: los PDF en blob: heredan esta política y el visor dejaría de
    # funcionar. La protección contra incrustar el sistema la da X-Frame-Options: DENY.
    "base-uri 'self'; form-action 'self'"
)


def registrar_middleware(app: FastAPI):

    @app.middleware("http")
    async def seguridad(request: Request, call_next):
        path = request.url.path
        es_api = path.startswith("/api/")

        if es_api:
            if not _limite_api.permitir(ip_cliente(request)):
                return JSONResponse({"detail": "Demasiadas peticiones. Espera un momento."}, status_code=429,
                                    headers={"Retry-After": "30"})
            # CSRF: toda escritura debe venir de nuestro propio JavaScript (cabecera personalizada).
            # Un formulario o enlace de otro sitio no puede añadir esta cabecera.
            if request.method not in _METODOS_SEGUROS and request.headers.get("x-requested-with") != "0808":
                return JSONResponse({"detail": "Petición rechazada."}, status_code=403)

        response = await call_next(request)

        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if COOKIE_SECURE:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        if es_api:
            h.setdefault("Cache-Control", "no-store")
        elif path.startswith("/sistema"):
            h.setdefault("Content-Security-Policy", CSP_SISTEMA)
        elif path == "/" or path.endswith(".html"):
            h.setdefault("Content-Security-Policy", CSP_LANDING)
        return response
