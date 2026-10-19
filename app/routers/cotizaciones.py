"""Pedidos (cotizaciones). Se pueden editar mientras estén pendientes y luego despacharse como venta."""
from fastapi import APIRouter, Depends, HTTPException, Response

from app.database import db, fix_id, oid
from app.models import VentaCreate
from app.pdf_generator import generar_factura_pdf
from app.services.documentos import telefono_whatsapp
from app.security import es_admin, exigir_dueno_o_admin, get_current_user
from app.services.inventario import (
    ahora, costo_estimado, evaluar_stock, limpiar_items, normalizar_pago,
    resumen_empaques, resumen_inventario, siguiente_consecutivo,
)

router = APIRouter(prefix="/api/cotizaciones", tags=["pedidos"])


def _pedido_o_404(cotizacion_id: str) -> dict:
    pedido = db.cotizaciones.find_one({"_id": oid(cotizacion_id)})
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return pedido


@router.post("", status_code=201)
def registrar_cotizacion(cotizacion: VentaCreate, user: dict = Depends(get_current_user)):
    if not cotizacion.items:
        raise HTTPException(status_code=400, detail="El pedido debe tener al menos un producto.")
    vendedor = (cotizacion.vendedor or user["username"]) if es_admin(user) else user["username"]
    items = limpiar_items(cotizacion.items)
    es_obsequio = cotizacion.tipo_venta == "Obsequio"
    consecutivo = siguiente_consecutivo("cotizacion_num")

    res = db.cotizaciones.insert_one({
        "consecutivo_str": consecutivo,
        "fecha": cotizacion.fecha,
        "cliente": cotizacion.cliente or "Cliente General",
        "vendedor": vendedor,
        "tipo_pago": normalizar_pago(cotizacion.tipo_pago, es_obsequio),
        "tipo_venta": cotizacion.tipo_venta or "Normal",
        "estado": "Pendiente",
        "total_venta": 0.0 if es_obsequio else sum(i["subtotal"] for i in items),
        "items": items,
        "creado_en": ahora(),
    })
    return {"id": str(res.inserted_id), "consecutivo": consecutivo}


@router.get("")
def listar_cotizaciones(user: dict = Depends(get_current_user)):
    filtro = {} if es_admin(user) else {"vendedor": user["username"]}
    salida = []
    for c in db.cotizaciones.find(filtro, {"historial_ediciones": 0}).sort("fecha", -1):
        c = fix_id(c)
        if c.get("tipo_pago") == "Efectivo":
            c["tipo_pago"] = "Contado"
        c.setdefault("estado", "Pendiente")
        salida.append(c)
    return salida


@router.put("/{cotizacion_id}")
def editar_pedido(cotizacion_id: str, datos: VentaCreate, user: dict = Depends(get_current_user)):
    """Edita un pedido que todavía NO se ha despachado, conservando su consecutivo."""
    pedido = _pedido_o_404(cotizacion_id)
    estado = pedido.get("estado", "Pendiente")
    if estado != "Pendiente":
        raise HTTPException(status_code=400, detail=f"Solo se pueden editar pedidos pendientes. Este pedido está '{estado}'.")
    exigir_dueno_o_admin(user, pedido)
    if not datos.items:
        raise HTTPException(status_code=400, detail="El pedido debe tener al menos un producto. Si ya no aplica, anúlalo.")

    items = limpiar_items(datos.items)
    es_obsequio = datos.tipo_venta == "Obsequio"
    total_nuevo = 0.0 if es_obsequio else sum(i["subtotal"] for i in items)

    res = db.cotizaciones.update_one(
        {"_id": pedido["_id"], "estado": {"$in": ["Pendiente", None]}},  # evita editar si lo despacharon mientras tanto
        {
            "$set": {
                "cliente": datos.cliente or "Cliente General",
                "tipo_pago": normalizar_pago(datos.tipo_pago, es_obsequio),
                "tipo_venta": datos.tipo_venta or "Normal",
                "total_venta": total_nuevo,
                "items": items,
                "editado_en": ahora(),
                "editado_por": user["username"],
            },
            "$push": {"historial_ediciones": {
                "fecha": ahora(), "usuario": user["username"],
                "total_anterior": float(pedido.get("total_venta", 0.0)), "total_nuevo": total_nuevo,
                "items_anteriores": pedido.get("items", []),
            }},
            # consecutivo_str, fecha, vendedor y creado_en NO se tocan
        },
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=409, detail="El pedido cambió de estado mientras lo editabas. Recarga la lista.")
    return {"id": cotizacion_id, "consecutivo": pedido.get("consecutivo_str", ""), "total_venta": total_nuevo,
            "mensaje": "Pedido actualizado correctamente"}


@router.post("/{cotizacion_id}/despachar")
def despachar_pedido(cotizacion_id: str, user: dict = Depends(get_current_user)):
    pedido = _pedido_o_404(cotizacion_id)
    exigir_dueno_o_admin(user, pedido)

    # Se marca primero como "Despachando" de forma atómica: si dos personas pulsan
    # "Despachar" a la vez, solo una genera la venta.
    tomado = db.cotizaciones.find_one_and_update(
        {"_id": pedido["_id"], "estado": {"$in": ["Pendiente", None]}},
        {"$set": {"estado": "Despachando"}},
    )
    if not tomado:
        raise HTTPException(status_code=400, detail=f"Este pedido ya está '{pedido.get('estado')}' y no se puede despachar.")

    try:
        items = pedido.get("items", [])
        resumen_cafe = resumen_inventario()
        resumen_emp = resumen_empaques()
        alcanza, faltantes = evaluar_stock(items, resumen_cafe, resumen_emp)
        costo_est = costo_estimado(items, resumen_cafe, resumen_emp)

        tipo_venta = pedido.get("tipo_venta", "Normal")
        tipo_pago = normalizar_pago(pedido.get("tipo_pago", "Contado"), tipo_venta == "Obsequio")
        total_venta = float(pedido.get("total_venta", 0.0))
        consecutivo_venta = siguiente_consecutivo("factura_num")
        estado_despacho = "Completo" if alcanza else "Pendiente"

        res_venta = db.ventas.insert_one({
            "consecutivo_str": consecutivo_venta,
            "pedido_origen_id": str(pedido["_id"]),
            "consecutivo_pedido": pedido.get("consecutivo_str", ""),
            "fecha": ahora().strftime("%Y-%m-%d"),
            "cliente": pedido.get("cliente", "Cliente General"),
            "vendedor": pedido.get("vendedor", user["username"]),
            "tipo_pago": tipo_pago,
            "tipo_venta": tipo_venta,
            "estado_despacho": estado_despacho,
            "faltantes": faltantes,
            "estado_credito": "Pendiente" if (tipo_pago == "Crédito" and tipo_venta != "Obsequio") else "N/A",
            "total_venta": total_venta,
            "costo_estimado": costo_est,
            "ganancia": total_venta - costo_est,
            "items": items,
            "creado_en": ahora(),
        })
    except Exception:
        db.cotizaciones.update_one({"_id": pedido["_id"]}, {"$set": {"estado": "Pendiente"}})
        raise

    db.cotizaciones.update_one({"_id": pedido["_id"]}, {"$set": {
        "estado": "Despachado", "venta_asociada_id": str(res_venta.inserted_id),
    }})
    return {"id_venta": str(res_venta.inserted_id), "consecutivo": consecutivo_venta,
            "estado_despacho": estado_despacho, "mensaje": "Pedido despachado y convertido a venta exitosamente"}


@router.get("/{cotizacion_id}/pdf")
def descargar_cotizacion_pdf(cotizacion_id: str, user: dict = Depends(get_current_user)):
    pedido = _pedido_o_404(cotizacion_id)
    exigir_dueno_o_admin(user, pedido)
    pdf_bytes = generar_factura_pdf(pedido, pedido.get("items", []), es_cotizacion=True)
    num = pedido.get("consecutivo_str", str(cotizacion_id)[:8])
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename=Pedido_{num}.pdf"})


@router.get("/{cotizacion_id}/whatsapp")
def contacto_whatsapp_pedido(cotizacion_id: str, user: dict = Depends(get_current_user)):
    pedido = _pedido_o_404(cotizacion_id)
    exigir_dueno_o_admin(user, pedido)
    if pedido.get("estado") == "Anulado":
        raise HTTPException(status_code=400, detail="El pedido está anulado; no se puede enviar.")
    return {"telefono": telefono_whatsapp(pedido.get("cliente", "")),
            "cliente": pedido.get("cliente", ""), "numero": pedido.get("consecutivo_str", ""),
            "total": float(pedido.get("total_venta", 0.0))}


@router.put("/{cotizacion_id}/anular")
@router.delete("/{cotizacion_id}")
def anular_cotizacion(cotizacion_id: str, user: dict = Depends(get_current_user)):
    pedido = _pedido_o_404(cotizacion_id)
    exigir_dueno_o_admin(user, pedido)
    if pedido.get("estado") in ("Despachado", "Despachando"):
        raise HTTPException(status_code=400, detail="Este pedido ya fue despachado; anula la venta en su lugar.")
    db.cotizaciones.update_one({"_id": pedido["_id"]}, {"$set": {
        "estado": "Anulado", "total_venta": 0.0, "anulado_en": ahora(), "anulado_por": user["username"],
    }})
    return {"mensaje": "Pedido anulado correctamente"}
