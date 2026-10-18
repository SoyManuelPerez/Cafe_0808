"""Ventas. Un vendedor solo ve y gestiona sus propias ventas; el admin ve todas."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.database import db, fix_id, oid
from app.models import EditarDetallesVenta, VentaCreate
from app.pdf_generator import generar_factura_pdf
from app.services.documentos import telefono_whatsapp, url_publica
from app.security import es_admin, exigir_dueno_o_admin, get_current_user, require_admin
from app.services.inventario import (
    ahora, costo_estimado, evaluar_stock, limpiar_items, normalizar_pago,
    resumen_empaques, resumen_inventario, siguiente_consecutivo,
)

router = APIRouter(prefix="/api", tags=["ventas"])

_CAMPOS_SOLO_ADMIN = ("costo_estimado", "ganancia", "costo_envio_asociado")


def _venta_o_404(venta_id: str) -> dict:
    venta = db.ventas.find_one({"_id": oid(venta_id)})
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return venta


@router.get("/reportes/resumen-ventas", dependencies=[Depends(require_admin)])
def obtener_resumen_ventas():
    resultado = list(db.ventas.aggregate([
        {"$match": {"tipo_venta": {"$ne": "Anulado"}, "estado_despacho": {"$ne": "Anulado"}}},
        {"$group": {"_id": None, "total_ingresos": {"$sum": "$total_venta"},
                    "total_ganancias": {"$sum": "$ganancia"}, "cantidad_ventas": {"$sum": 1}}},
    ]))
    if not resultado:
        return {"total_ingresos": 0.0, "total_ganancias": 0.0, "cantidad_ventas": 0}
    res = resultado[0]
    res.pop("_id", None)
    return res


@router.post("/ventas", status_code=201)
def registrar_venta(venta: VentaCreate, user: dict = Depends(get_current_user)):
    # El vendedor es quien tiene la sesión. Solo el admin puede registrar a nombre de otro.
    vendedor = (venta.vendedor or user["username"]) if es_admin(user) else user["username"]
    items = limpiar_items(venta.items)

    resumen_cafe = resumen_inventario()
    resumen_emp = resumen_empaques()
    alcanza, faltantes = evaluar_stock(items, resumen_cafe, resumen_emp)

    es_obsequio = venta.tipo_venta == "Obsequio"
    total_venta = 0.0 if es_obsequio else sum(i["subtotal"] for i in items)
    costo_est = costo_estimado(items, resumen_cafe, resumen_emp)
    tipo_pago = normalizar_pago(venta.tipo_pago, es_obsequio)
    consecutivo = siguiente_consecutivo("factura_num")
    estado_despacho = "Completo" if alcanza else "Pendiente"

    res = db.ventas.insert_one({
        "consecutivo_str": consecutivo,
        "fecha": venta.fecha,
        "cliente": venta.cliente or "Cliente General",
        "vendedor": vendedor,
        "tipo_pago": tipo_pago,
        "tipo_venta": venta.tipo_venta or "Normal",
        "estado_despacho": estado_despacho,
        "faltantes": faltantes,
        "estado_credito": "Pendiente" if (tipo_pago == "Crédito" and not es_obsequio) else "N/A",
        "total_venta": total_venta,
        "costo_estimado": costo_est,
        "ganancia": total_venta - costo_est,
        "items": items,
        "creado_en": ahora(),
    })
    return {"id": str(res.inserted_id), "consecutivo": consecutivo, "estado_despacho": estado_despacho}


@router.get("/ventas")
def listar_ventas(user: dict = Depends(get_current_user)):
    admin = es_admin(user)
    filtro = {} if admin else {"vendedor": user["username"]}
    salida = []
    for v in db.ventas.find(filtro).sort("fecha", -1):
        v = fix_id(v)
        if v.get("tipo_pago") == "Efectivo":
            v["tipo_pago"] = "Contado"
        if admin:
            v["costo_envio_asociado"] = 0.0
            v["ganancia"] = float(v.get("ganancia", 0.0))
        else:
            for campo in _CAMPOS_SOLO_ADMIN:
                v.pop(campo, None)
        salida.append(v)
    return salida


@router.put("/ventas/{venta_id}/completar-despacho", dependencies=[Depends(require_admin)])
def completar_despacho_venta(venta_id: str):
    venta = _venta_o_404(venta_id)
    if venta.get("estado_despacho") == "Completo":
        return {"mensaje": "La venta ya está completada"}
    if venta.get("estado_despacho") == "Anulado":
        raise HTTPException(status_code=400, detail="La venta está anulada.")

    alcanza, faltantes = evaluar_stock(venta.get("items", []))
    if "cafe_g" in faltantes:
        raise HTTPException(status_code=400, detail="Inventario de café todavía insuficiente para completar el despacho.")
    if faltantes:
        nombre = next(iter(faltantes)).replace("_", " ").title()
        raise HTTPException(status_code=400, detail=f"Stock insuficiente de {nombre} para completar.")

    db.ventas.update_one({"_id": venta["_id"]}, {"$set": {"estado_despacho": "Completo", "faltantes": {}}})
    return {"mensaje": "Venta completada y stock descontado exitosamente"}


@router.put("/ventas/{venta_id}/pagar-credito")
def pagar_credito(venta_id: str, user: dict = Depends(get_current_user)):
    venta = _venta_o_404(venta_id)
    exigir_dueno_o_admin(user, venta)
    db.ventas.update_one({"_id": venta["_id"]}, {"$set": {"estado_credito": "Pagado"}})
    return {"mensaje": "Crédito pagado"}


@router.put("/ventas/{venta_id}/anular")
@router.delete("/ventas/{venta_id}")
def anular_venta(venta_id: str, user: dict = Depends(get_current_user)):
    venta = _venta_o_404(venta_id)
    exigir_dueno_o_admin(user, venta)
    db.ventas.update_one({"_id": venta["_id"]}, {"$set": {
        "tipo_venta": "Anulado", "estado_despacho": "Anulado", "estado_credito": "Anulado",
        "total_venta": 0.0, "costo_estimado": 0.0, "ganancia": 0.0,
        "anulado_en": ahora(), "anulado_por": user["username"],
    }})
    return {"mensaje": "Venta anulada correctamente"}


@router.get("/ventas/{venta_id}/pdf")
def descargar_factura(venta_id: str, user: dict = Depends(get_current_user)):
    venta = _venta_o_404(venta_id)
    exigir_dueno_o_admin(user, venta)
    pdf_bytes = generar_factura_pdf(venta, venta.get("items", []), es_cotizacion=False)
    num = venta.get("consecutivo_str", str(venta_id)[:8])
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename=Factura_{num}.pdf"})


@router.get("/ventas/{venta_id}/whatsapp")
def enlace_whatsapp_venta(venta_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Enlace firmado para que el cliente vea su factura, y su celular si está registrado."""
    venta = _venta_o_404(venta_id)
    exigir_dueno_o_admin(user, venta)
    if venta.get("tipo_venta") == "Anulado":
        raise HTTPException(status_code=400, detail="La venta está anulada; no se puede enviar.")
    url = url_publica(request, "venta", str(venta["_id"]))
    return {"url": url, "telefono": telefono_whatsapp(venta.get("cliente", "")),
            "cliente": venta.get("cliente", ""), "numero": venta.get("consecutivo_str", ""),
            "total": float(venta.get("total_venta", 0.0))}


@router.put("/ventas/{venta_id}/editar-detalles")
def editar_detalles_venta(venta_id: str, data: EditarDetallesVenta, user: dict = Depends(get_current_user)):
    venta = _venta_o_404(venta_id)
    exigir_dueno_o_admin(user, venta)
    if venta.get("tipo_venta") == "Anulado":
        raise HTTPException(status_code=400, detail="No se puede editar una venta anulada.")

    if venta.get("tipo_venta") == "Obsequio":
        tipo_pago, estado_credito = "N/A", "N/A"
    else:
        tipo_pago = normalizar_pago(data.tipo_pago, False)
        if tipo_pago == "Crédito":
            estado_credito = venta.get("estado_credito") if venta.get("estado_credito") in ("Pendiente", "Pagado") else "Pendiente"
        else:
            estado_credito = "N/A"

    db.ventas.update_one({"_id": venta["_id"]}, {"$set": {
        "cliente": data.cliente, "tipo_pago": tipo_pago, "estado_credito": estado_credito,
    }})
    return {"mensaje": "Venta actualizada correctamente"}
