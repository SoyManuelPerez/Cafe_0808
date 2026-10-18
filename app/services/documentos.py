"""Enlaces para compartir facturas y pedidos por WhatsApp.

El enlace lleva un token firmado (no adivinable) que solo abre ESE documento y vence.
Así el cliente puede ver su factura sin tener usuario en el sistema.
"""
import re
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException

from app.config import SECRET_KEY
from app.database import db, oid
from app.pdf_generator import generar_factura_pdf

_AUD = "documento-0808"
DIAS_VIGENCIA = 30
TIPOS = {"venta": "ventas", "pedido": "cotizaciones"}


def crear_token(tipo: str, doc_id: str) -> str:
    return jwt.encode({
        "t": tipo, "id": str(doc_id), "aud": _AUD,
        "exp": datetime.now(timezone.utc) + timedelta(days=DIAS_VIGENCIA),
    }, SECRET_KEY, algorithm="HS256")


def leer_token(token: str):
    try:
        datos = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], audience=_AUD)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=410, detail="Este enlace ya venció. Pide uno nuevo a 0808 Café.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    if datos.get("t") not in TIPOS:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return datos["t"], datos["id"]


def pdf_desde_token(token: str):
    tipo, doc_id = leer_token(token)
    doc = db[TIPOS[tipo]].find_one({"_id": oid(doc_id)})
    if not doc or doc.get("tipo_venta") == "Anulado" or doc.get("estado") == "Anulado":
        raise HTTPException(status_code=404, detail="Documento no disponible")
    nombre = ("Factura_" if tipo == "venta" else "Pedido_") + doc.get("consecutivo_str", doc_id[:8])
    return generar_factura_pdf(doc, doc.get("items", []), es_cotizacion=(tipo == "pedido")), nombre


def url_publica(request, tipo: str, doc_id: str) -> str:
    """URL absoluta del documento. Detrás del proxy de Render se respeta https y el dominio real."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}/api/public/documento/{crear_token(tipo, doc_id)}"


def telefono_whatsapp(nombre_cliente: str) -> str:
    """Celular del cliente en formato internacional (Colombia por defecto), o '' si no hay."""
    if not nombre_cliente:
        return ""
    cli = db.clientes.find_one({"nombre": nombre_cliente}, {"celular": 1}) or \
        db.clientes.find_one({"nombre": {"$regex": f"^{re.escape(nombre_cliente.strip())}$", "$options": "i"}}, {"celular": 1})
    digitos = re.sub(r"\D", "", (cli or {}).get("celular", "") or "")
    if len(digitos) == 10 and digitos.startswith("3"):
        return "57" + digitos
    return digitos if len(digitos) >= 11 else ""
