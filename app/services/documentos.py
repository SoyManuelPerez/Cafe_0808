"""Datos para enviar facturas y pedidos por WhatsApp."""
import re

from app.database import db


def telefono_whatsapp(nombre_cliente: str) -> str:
    """Celular del cliente en formato internacional (Colombia por defecto), o '' si no hay."""
    if not nombre_cliente:
        return ""
    cli = db.clientes.find_one({"nombre": nombre_cliente}, {"celular": 1}) or         db.clientes.find_one({"nombre": {"$regex": f"^{re.escape(nombre_cliente.strip())}$", "$options": "i"}}, {"celular": 1})
    return normalizar_celular((cli or {}).get("celular", ""))


def normalizar_celular(valor: str) -> str:
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) == 10 and digitos.startswith("3"):
        return "57" + digitos
    return digitos if len(digitos) >= 11 else ""
