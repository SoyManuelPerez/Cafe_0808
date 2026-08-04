import os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://Cafe0808:AdminCafe0808@bdcafe0808.ivz1n4f.mongodb.net/?appName=BDCAFE0808")
DB_NAME = os.getenv("DB_NAME", "gestion_cafe")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def get_db():
    return db

def fix_id(doc):
    """Convierte el '_id' ObjectId de MongoDB a un string 'id'."""
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc