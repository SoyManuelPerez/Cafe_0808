"""Otros gastos (solo administradores)."""
from fastapi import APIRouter, Depends, HTTPException

from app.database import db, fix_id, oid
from app.models import GastoCreate
from app.security import require_admin
from app.services.inventario import ahora

router = APIRouter(prefix="/api/gastos", tags=["gastos"], dependencies=[Depends(require_admin)])


@router.post("", status_code=201)
def crear_gasto(gasto: GastoCreate):
    if gasto.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto del gasto debe ser mayor a 0.")
    res = db.gastos.insert_one({"monto": gasto.monto, "fecha": gasto.fecha, "observacion": gasto.observacion, "creado_en": ahora()})
    return {"id": str(res.inserted_id), "mensaje": "Gasto registrado exitosamente"}


@router.get("")
def listar_gastos():
    return [fix_id(g) for g in db.gastos.find().sort("fecha", -1)]


@router.delete("/{gasto_id}")
def eliminar_gasto(gasto_id: str):
    res = db.gastos.delete_one({"_id": oid(gasto_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return {"mensaje": "Gasto eliminado correctamente"}
