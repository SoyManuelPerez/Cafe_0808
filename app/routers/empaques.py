"""Compras y existencias de bolsas y etiquetas."""
from fastapi import APIRouter, Depends

from app.database import db, fix_id
from app.models import AjusteEmpaque, CompraEmpaqueCreate
from app.security import get_current_user, require_admin
from app.services.inventario import ahora, resumen_empaques

router = APIRouter(prefix="/api", tags=["empaques"])


@router.post("/compras-empaques", status_code=201, dependencies=[Depends(require_admin)])
def crear_compra_empaque(compra: CompraEmpaqueCreate):
    res = db.compras_empaques.insert_one({
        "fecha": compra.fecha,
        "tipo_empaque": compra.tipo_empaque,
        "cantidad": compra.cantidad,
        "costo_total": compra.costo_total,
        "costo_unitario": compra.costo_total / compra.cantidad,
        "creado_en": ahora(),
    })
    return {"id": str(res.inserted_id)}


@router.get("/compras-empaques", dependencies=[Depends(require_admin)])
def listar_compras_empaques():
    return [fix_id(c) for c in db.compras_empaques.find().sort("fecha", -1)]


# Lo usan también los vendedores para calcular "Venta al costo".
@router.get("/empaques/resumen", dependencies=[Depends(get_current_user)])
def obtener_resumen_empaques():
    return resumen_empaques()


@router.put("/empaques/ajuste-manual", dependencies=[Depends(require_admin)])
def ajustar_empaque_manual(data: AjusteEmpaque):
    db.ajustes_empaques.update_one(
        {"tipo_empaque": data.tipo_empaque},
        {"$set": {"disponibles": data.disponibles, "costo_unitario": data.costo_unitario}},
        upsert=True,
    )
    return {"mensaje": f"Empaque {data.tipo_empaque} actualizado correctamente"}
