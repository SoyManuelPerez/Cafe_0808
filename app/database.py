import os
from pymongo import MongoClient

# Lee la variable de entorno 'MONGO_URI' configurada en Render.
# Si estás ejecutando localmente y no existe la variable, usará 'mongodb://localhost:27017' por defecto.
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "gestion_cafe")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def get_db():
    return db

def fix_id(doc):
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc
