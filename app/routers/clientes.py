"""Clientes (todos los usuarios con sesión)."""
from fastapi import APIRouter, Depends, HTTPException

from app.database import db, fix_id, oid
from app.models import ClienteCreate
from app.security import get_current_user
from app.services.inventario import ahora

router = APIRouter(prefix="/api/clientes", tags=["clientes"], dependencies=[Depends(get_current_user)])


@router.post("", status_code=201)
def crear_cliente(cli: ClienteCreate):
    celular = (cli.celular or "").strip()
    if celular:
        existente = db.clientes.find_one({"celular": celular})
        if existente:
            raise HTTPException(
                status_code=400,
                detail=f"⚠️ El número de teléfono {celular} ya pertenece al cliente: '{existente.get('nombre', 'Desconocido')}'.",
            )
    doc = {"nombre": cli.nombre, "celular": celular, "creado_en": ahora()}
    res = db.clientes.insert_one(doc)
    return {"id": str(res.inserted_id), "nombre": doc["nombre"]}


@router.get("")
def listar_clientes():
    return [fix_id(c) for c in db.clientes.find().sort("nombre", 1)]


@router.put("/{cliente_id}")
def editar_cliente(cliente_id: str, cli: ClienteCreate):
    res = db.clientes.update_one({"_id": oid(cliente_id)}, {"$set": {"nombre": cli.nombre, "celular": (cli.celular or "").strip()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"mensaje": "Cliente actualizado exitosamente"}


@router.delete("/{cliente_id}")
def eliminar_cliente(cliente_id: str):
    res = db.clientes.delete_one({"_id": oid(cliente_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"mensaje": "Cliente eliminado"}
