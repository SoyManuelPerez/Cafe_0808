"""Datos públicos para la landing. Solo nombre, presentación y precio: nunca costos."""
import threading
import time

from fastapi import APIRouter, Response

from app.database import db

router = APIRouter(prefix="/api/public", tags=["público"])

_CACHE_SEG = 60
_cache = {"t": 0.0, "datos": None}
_lock = threading.Lock()


@router.get("/precios")
def precios_publicos(response: Response):
    """Precios vigentes del sistema. Se guardan 60 s en memoria para que muchas visitas
    a la landing no golpeen la base de datos."""
    with _lock:
        if _cache["datos"] is None or time.monotonic() - _cache["t"] > _CACHE_SEG:
            try:
                _cache["datos"] = [
                    {"nombre": p.get("nombre", ""), "gramaje": int(p.get("gramaje") or 0),
                     "precio": float(p.get("precio_venta") or 0)}
                    for p in db.productos.find({}, {"nombre": 1, "gramaje": 1, "precio_venta": 1})
                    if p.get("precio_venta")
                ]
            except Exception:
                _cache["datos"] = _cache["datos"] or []
            _cache["t"] = time.monotonic()
        datos = _cache["datos"]
    response.headers["Cache-Control"] = "public, max-age=60"
    return datos
