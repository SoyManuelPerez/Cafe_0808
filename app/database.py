"""Conexión única a MongoDB (pool compartido por todos los hilos) e índices."""
import logging
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException
from pymongo import MongoClient, ASCENDING, DESCENDING

from app.config import MONGO_URI, DB_NAME, MONGO_POOL_SIZE

log = logging.getLogger("cafe0808")

# Un solo cliente para toda la app: reutiliza conexiones en vez de abrir una por petición.
client = MongoClient(
    MONGO_URI,
    maxPoolSize=MONGO_POOL_SIZE,
    serverSelectionTimeoutMS=8000,
    connectTimeoutMS=8000,
    socketTimeoutMS=20000,
    retryWrites=True,
)
db = client[DB_NAME]


def get_db():
    return db


def fix_id(doc):
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc


def oid(valor: str) -> ObjectId:
    """Convierte un id de la URL a ObjectId; si no es válido responde 400 (no 500)."""
    try:
        return ObjectId(valor)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Identificador inválido")


def crear_indices():
    """Índices para que las consultas sigan siendo rápidas con muchos datos y usuarios."""
    indices = [
        ("usuarios", [("username", ASCENDING)], {"unique": True}),
        ("clientes", [("nombre", ASCENDING)], {}),
        ("clientes", [("celular", ASCENDING)], {}),
        ("productos", [("nombre", ASCENDING)], {}),
        ("ventas", [("fecha", DESCENDING)], {}),
        ("ventas", [("vendedor", ASCENDING), ("fecha", DESCENDING)], {}),
        ("ventas", [("estado_despacho", ASCENDING), ("tipo_venta", ASCENDING)], {}),
        ("ventas", [("items.producto_id", ASCENDING)], {}),
        ("cotizaciones", [("fecha", DESCENDING)], {}),
        ("cotizaciones", [("vendedor", ASCENDING), ("estado", ASCENDING)], {}),
        ("compras", [("producto_nombre", ASCENDING)], {}),
        ("compras", [("fecha", DESCENDING)], {}),
        ("compras_empaques", [("tipo_empaque", ASCENDING), ("fecha", DESCENDING)], {}),
        ("ajustes_inventario", [("creado_en", DESCENDING)], {}),
        ("gastos", [("fecha", DESCENDING)], {}),
    ]
    for coleccion, claves, opciones in indices:
        try:
            db[coleccion].create_index(claves, **opciones)
        except Exception as e:  # la app arranca aunque un índice falle
            log.error("No se pudo crear índice %s %s: %s", coleccion, claves, e)
