"""Productos y compras de café."""
from fastapi import APIRouter, Depends, HTTPException

from app.database import db, fix_id, oid
from app.models import CompraCreate, CostoLibra, ProductoCreate, ProductoUpdate
from app.security import get_current_user, require_admin
from app.services.inventario import ahora

router = APIRouter(prefix="/api", tags=["productos"])


# ---------------- Productos ----------------

@router.get("/productos", dependencies=[Depends(get_current_user)])
def listar_productos():
    return [fix_id(p) for p in db.productos.find()]


@router.get("/productos/unicos", dependencies=[Depends(require_admin)])
def listar_productos_unicos():
    return list(db.productos.aggregate([
        {"$group": {
            "_id": "$nombre",
            "id": {"$first": {"$toString": "$_id"}},
            "nombre": {"$first": "$nombre"},
            "costo_por_libra": {"$first": "$costo_por_libra"},
        }}
    ]))


@router.post("/productos", status_code=201, dependencies=[Depends(require_admin)])
def crear_producto(prod: ProductoCreate):
    doc = prod.model_dump()
    doc["costo_por_libra"] = doc.get("costo_por_libra") or 0.0
    doc["creado_en"] = ahora()
    res = db.productos.insert_one(doc)
    return {"id": str(res.inserted_id)}


@router.put("/productos/actualizar-costo-libra", dependencies=[Depends(require_admin)])
def actualizar_costo_libra_manual(data: CostoLibra):
    db.productos.update_many({"nombre": data.nombre}, {"$set": {"costo_por_libra": data.costo_por_libra}})
    return {"mensaje": "Costo por libra actualizado"}


@router.put("/productos/{prod_id}", dependencies=[Depends(require_admin)])
def editar_producto(prod_id: str, prod: ProductoUpdate):
    res = db.productos.update_one({"_id": oid(prod_id)}, {"$set": {"nombre": prod.nombre, "precio_venta": prod.precio_venta}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"mensaje": "Producto actualizado"}


@router.delete("/productos/{prod_id}", dependencies=[Depends(require_admin)])
def eliminar_producto(prod_id: str):
    _id = oid(prod_id)
    if db.ventas.count_documents({"items.producto_id": prod_id}, limit=1) > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el producto tiene ventas asociadas.")
    db.productos.delete_one({"_id": _id})
    return {"mensaje": "Producto eliminado exitosamente"}


# ---------------- Compras de café ----------------

@router.post("/compras", status_code=201, dependencies=[Depends(require_admin)])
def crear_compra(compra: CompraCreate):
    gramos = compra.libras * 500.0
    costo_por_libra = compra.costo_total / compra.libras

    nombre_producto = "Materia Prima General"
    if compra.producto_id:
        prod = db.productos.find_one({"_id": oid(compra.producto_id)})
        if prod:
            nombre_producto = prod["nombre"]
            db.productos.update_many({"nombre": prod["nombre"]}, {"$set": {"costo_por_libra": costo_por_libra}})

    res = db.compras.insert_one({
        "fecha": compra.fecha,
        "libras": compra.libras,
        "gramos": gramos,
        "costo_total": compra.costo_total,
        "costo_por_gramo": compra.costo_total / gramos,
        "costo_por_libra": costo_por_libra,
        "producto_id": compra.producto_id,
        "producto_nombre": nombre_producto,
        "creado_en": ahora(),
    })
    return {"id": str(res.inserted_id)}


@router.get("/compras", dependencies=[Depends(require_admin)])
def listar_compras():
    # Se excluyen ajustes manuales antiguos (gramos negativos): no son compras reales
    compras = list(db.compras.find({"gramos": {"$gt": 0}}).sort("fecha", -1))
    nombres = {str(p["_id"]): p["nombre"] for p in db.productos.find({}, {"nombre": 1})}
    for c in compras:
        if not c.get("producto_nombre"):
            c["producto_nombre"] = nombres.get(str(c.get("producto_id", "")), "Materia Prima General")
    return [fix_id(c) for c in compras]
