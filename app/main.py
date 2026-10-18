"""Punto de entrada: arma la app con sus módulos.

Estructura:
    app/config.py        variables de entorno
    app/database.py      conexión a MongoDB e índices
    app/security.py      sesión, roles, contraseñas, límites anti-abuso
    app/middleware.py    cabeceras de seguridad, CSRF y límite por IP
    app/models.py        validación de datos de entrada
    app/services/        cálculos de inventario y costos
    app/routers/         una ruta por módulo (ventas, pedidos, clientes, ...)
"""
import logging
import os
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import ADMIN_INITIAL_PASSWORD, ENABLE_DOCS, LANDING_DIR, STATIC_DIR
from app.database import crear_indices, db
from app.middleware import registrar_middleware
from app.routers import (
    auth, clientes, cotizaciones, empaques, gastos, inventario, pages, productos, public, usuarios, ventas,
)
from app.security import hash_password
from app.services.inventario import ahora

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("cafe0808")


def asegurar_admin():
    """Crea el admin solo si la base no tiene usuarios. Nunca cambia una contraseña existente."""
    try:
        if db.usuarios.count_documents({}, limit=1) == 0:
            db.usuarios.insert_one({
                "username": "admin", "password_hash": hash_password(ADMIN_INITIAL_PASSWORD),
                "rol": "admin", "token_version": 0, "creado_en": ahora(),
            })
            log.warning("Se creó el usuario 'admin'. Cambia su contraseña desde Usuarios.")
        else:
            db.usuarios.update_one({"username": "admin"}, {"$set": {"rol": "admin"}})
    except Exception as e:
        log.error("Error verificando usuario admin inicial: %s", e)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # Más hilos para atender peticiones simultáneas (pymongo es bloqueante).
    anyio.to_thread.current_default_thread_limiter().total_tokens = 100
    await anyio.to_thread.run_sync(crear_indices)
    await anyio.to_thread.run_sync(asegurar_admin)
    yield


class StaticCache(StaticFiles):
    """Archivos estáticos con caché del navegador (imágenes, CSS, JS)."""

    def __init__(self, *args, max_age: int = 86400, **kwargs):
        self.max_age = max_age
        super().__init__(*args, **kwargs)

    def file_response(self, full_path, *args, **kwargs):
        resp = super().file_response(full_path, *args, **kwargs)
        if str(full_path).endswith((".js", ".css")):
            # CSS/JS: el navegador pregunta si cambió (respuesta 304 si no). Así un cambio
            # publicado se ve de inmediato sin tener que limpiar caché.
            resp.headers["Cache-Control"] = "no-cache"
        else:
            resp.headers["Cache-Control"] = f"public, max-age={self.max_age}"
        return resp


app = FastAPI(
    title="0808 Café de Especialidad",
    lifespan=ciclo_de_vida,
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)

app.add_middleware(GZipMiddleware, minimum_size=1024)
registrar_middleware(app)

# Archivos estáticos
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticCache(directory=STATIC_DIR, max_age=3600), name="static")
app.mount("/assets", StaticCache(directory=os.path.join(LANDING_DIR, "assets"), max_age=86400), name="landing_assets")
# Ruta antigua de las imágenes de la landing (por si hay enlaces compartidos)
app.mount("/img", StaticCache(directory=os.path.join(LANDING_DIR, "assets", "img"), max_age=604800), name="landing_img")

# API
for modulo in (auth, usuarios, clientes, gastos, empaques, productos, inventario, ventas, cotizaciones, public):
    app.include_router(modulo.router)

# Páginas (al final: contiene la ruta comodín)
app.include_router(pages.router)
