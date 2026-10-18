"""Servidor LOCAL de prueba con base de datos simulada en memoria (no toca tu MongoDB real).

Sirve para revisar lo visual sin conexión a la base de datos. Los datos se borran al cerrarlo.

Uso:
    pip install -r requirements.txt -r requirements-dev.txt
    python scripts/servidor_prueba.py
Luego abre http://localhost:8808/sistema/

Usuarios de prueba (solo existen en esta base simulada):
    admin      / 0808cafe    -> rol administrador
    vendedor1  / ventas123   -> rol ventas
"""
import os
import sys

import mongomock
import pymongo

pymongo.MongoClient = mongomock.MongoClient  # antes de importar la app

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
os.environ.setdefault("SECRET_KEY", "clave-solo-para-pruebas-locales")

from app.database import db  # noqa: E402
from app.security import hash_password  # noqa: E402

USUARIOS = [("admin", "0808cafe", "admin"), ("vendedor1", "ventas123", "ventas")]
for usuario, clave, rol in USUARIOS:
    db.usuarios.insert_one({"username": usuario, "password_hash": hash_password(clave), "rol": rol, "token_version": 0})

for nombre, g, precio, costo in [("Bourbon Rosado", 250, 33000, 40000), ("Bourbon Rosado", 500, 60000, 40000),
                                 ("Chiroso", 250, 35000, 42000), ("Blend Castillo Caturra", 250, 27000, 30000)]:
    db.productos.insert_one({"nombre": nombre, "gramaje": g, "precio_venta": precio, "costo_por_libra": costo})
db.compras.insert_one({"fecha": "2026-10-01", "libras": 20, "gramos": 10000, "costo_total": 800000,
                       "producto_nombre": "Bourbon Rosado"})
db.clientes.insert_one({"nombre": "Cliente de prueba", "celular": "3000000000"})

import uvicorn  # noqa: E402
from app.main import app  # noqa: E402

print("Sistema de prueba: http://localhost:8808/sistema/   Landing: http://localhost:8808/")
uvicorn.run(app, host="127.0.0.1", port=8808, log_level="warning")
