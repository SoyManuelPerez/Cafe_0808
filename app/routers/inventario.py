"""Existencias de café y ajustes manuales."""
from fastapi import APIRouter, Depends, HTTPException

from app.database import db, fix_id
from app.models import AjusteInventarioCreate, DescuentoManual
from app.security import get_current_user, require_admin
from app.services.inventario import ahora, resumen_inventario

router = APIRouter(prefix="/api/inventario", tags=["inventario"])


@router.get("/resumen", dependencies=[Depends(get_current_user)])
def obtener_resumen_inventario():
    return resumen_inventario()


@router.post("/ajustar", status_code=201)
def ajustar_inventario_manual(ajuste: AjusteInventarioCreate, user: dict = Depends(require_admin)):
    """Suma o descuenta café del inventario SIN registrar una compra.
    No modifica costo_por_libra, ni la inversión, ni las ganancias."""
    nombre = ajuste.nombre.strip()
    tipo = (ajuste.tipo or "").strip().lower()

    if not nombre:
        raise HTTPException(status_code=400, detail="Debe seleccionar un café.")
    if tipo not in ("entrada", "salida"):
        raise HTTPException(status_code=400, detail="El tipo de ajuste debe ser 'entrada' o 'salida'.")
    if ajuste.libras <= 0:
        raise HTTPException(status_code=400, detail="La cantidad de libras debe ser mayor a 0.")
    if not db.productos.find_one({"nombre": nombre}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="El café seleccionado no existe.")

    gramos = round(ajuste.libras * 500.0, 2)
    if tipo == "salida":
        stock = resumen_inventario()["productos_stock"]
        disponible_g = next((p["gramos_disponibles"] for p in stock if p["nombre"] == nombre), 0.0)
        if gramos > disponible_g + 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"No puedes descontar {ajuste.libras} lbs: de '{nombre}' solo hay {round(disponible_g / 500.0, 1)} lbs disponibles.",
            )

    signo = 1 if tipo == "entrada" else -1
    res = db.ajustes_inventario.insert_one({
        "fecha": ahora().strftime("%Y-%m-%d"),
        "producto_nombre": nombre,
        "tipo": tipo,
        "libras": signo * ajuste.libras,
        "gramos": signo * gramos,
        "motivo": (ajuste.motivo or "").strip() or "Ajuste manual",
        "usuario": user["username"],
        "creado_en": ahora(),
    })
    accion = "sumaron" if tipo == "entrada" else "descontaron"
    return {"id": str(res.inserted_id), "mensaje": f"Se {accion} {ajuste.libras} lbs de {nombre} del inventario."}


@router.get("/ajustes", dependencies=[Depends(require_admin)])
def listar_ajustes_inventario():
    return [fix_id(a) for a in db.ajustes_inventario.find().sort("creado_en", -1).limit(100)]


@router.put("/descontar-manual")
def descontar_stock_manual(data: DescuentoManual, user: dict = Depends(require_admin)):
    """Compatibilidad con el endpoint anterior: delega en el ajuste manual (tipo salida)."""
    ajuste = AjusteInventarioCreate(nombre=data.nombre, libras=data.libras, tipo="salida",
                                    motivo=data.motivo or "Descuento manual")
    return ajustar_inventario_manual(ajuste, user)
