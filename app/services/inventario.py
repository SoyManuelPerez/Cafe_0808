"""Cálculos de inventario de café, empaques y costos de una venta.

Se usan desde ventas, pedidos y ajustes. Cada función hace pocas consultas agregadas
(en vez de una consulta por producto) para responder rápido aunque haya muchos datos.
"""
from datetime import datetime

from app.database import db

TIPOS_EMPAQUE = ("bolsa_250g", "bolsa_500g", "etiqueta_250g", "etiqueta_500g")
_FILTRO_DESPACHADAS = {"estado_despacho": {"$nin": ["Pendiente", "Anulado"]}, "tipo_venta": {"$ne": "Anulado"}}


def empaques_por_item(gramaje: int, cantidad: int) -> dict:
    """Bolsas y etiquetas que consume un ítem según su presentación."""
    req = dict.fromkeys(TIPOS_EMPAQUE, 0)
    if gramaje == 250:
        req["bolsa_250g"] += cantidad
        req["etiqueta_250g"] += cantidad
    elif gramaje == 500:
        req["bolsa_500g"] += cantidad
        req["etiqueta_500g"] += cantidad
    elif gramaje == 2500:
        req["etiqueta_500g"] += cantidad
    return req


def empaques_requeridos(items) -> dict:
    total = dict.fromkeys(TIPOS_EMPAQUE, 0)
    for it in items:
        for k, v in empaques_por_item(int(it.get("gramaje", 0)), int(it.get("cantidad", 0))).items():
            total[k] += v
    return total


# ---------------- Empaques ----------------

def resumen_empaques() -> dict:
    compras = {c["_id"]: c for c in db.compras_empaques.aggregate([
        {"$group": {"_id": "$tipo_empaque", "total_cant": {"$sum": "$cantidad"}, "total_costo": {"$sum": "$costo_total"}}}
    ])}

    ultimas = {c["_id"]: c.get("costo_unitario", 0.0) for c in db.compras_empaques.aggregate([
        {"$sort": {"fecha": -1, "_id": -1}},
        {"$group": {"_id": "$tipo_empaque", "costo_unitario": {"$first": "$costo_unitario"}}}
    ])}

    usados = dict.fromkeys(TIPOS_EMPAQUE, 0)
    for g in db.ventas.aggregate([
        {"$match": _FILTRO_DESPACHADAS},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.gramaje", "cant": {"$sum": "$items.cantidad"}}}
    ]):
        for k, v in empaques_por_item(int(g["_id"] or 0), int(g["cant"] or 0)).items():
            usados[k] += v

    ajustes = {a["tipo_empaque"]: a for a in db.ajustes_empaques.find({"tipo_empaque": {"$in": list(TIPOS_EMPAQUE)}})}

    resumen = {}
    for t in TIPOS_EMPAQUE:
        total_cant = compras.get(t, {}).get("total_cant", 0)
        if t in ajustes:
            disponibles = ajustes[t].get("disponibles", 0)
            costo_unitario = ajustes[t].get("costo_unitario", 0.0)
        else:
            disponibles = max(0, total_cant - usados[t])
            costo_unitario = float(ultimas.get(t) or 0.0)
        resumen[t] = {
            "comprados": total_cant,
            "usados": usados[t],
            "disponibles": disponibles,
            "costo_unitario": round(costo_unitario, 2),
        }
    return resumen


# ---------------- Café ----------------

def gramos_ajustados_por_producto() -> dict:
    """Ajustes manuales (entradas +, salidas -) por café, en gramos. NO son compras."""
    return {a["_id"]: a["total_g"] for a in db.ajustes_inventario.aggregate([
        {"$group": {"_id": "$producto_nombre", "total_g": {"$sum": "$gramos"}}}
    ]) if a["_id"]}


def resumen_inventario() -> dict:
    # Todas las compras (incluye ajustes antiguos guardados como compras negativas) -> solo STOCK
    dict_compras = {c["_id"]: c["total_g"] for c in db.compras.aggregate([
        {"$group": {"_id": "$producto_nombre", "total_g": {"$sum": "$gramos"}}}
    ]) if c["_id"]}

    # Solo compras reales (gramos > 0) -> COSTO PROMEDIO
    reales = list(db.compras.aggregate([
        {"$match": {"gramos": {"$gt": 0}}},
        {"$group": {"_id": None, "total_g": {"$sum": "$gramos"}, "total_costo": {"$sum": "$costo_total"}}}
    ]))
    total_comprado_real = reales[0]["total_g"] if reales else 0.0
    total_inversion_real = reales[0]["total_costo"] if reales else 0.0

    dict_ajustes = gramos_ajustados_por_producto()

    dict_usados = {v["_id"]: v["usados_g"] for v in db.ventas.aggregate([
        {"$match": _FILTRO_DESPACHADAS},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.nombre", "usados_g": {"$sum": "$items.gramos_totales"}}}
    ]) if v["_id"]}

    nombres = db.productos.distinct("nombre")
    tarjetas = []
    for nombre in nombres:
        disp_g = max(0.0, dict_compras.get(nombre, 0.0) + dict_ajustes.get(nombre, 0.0) - dict_usados.get(nombre, 0.0))
        tarjetas.append({"nombre": nombre, "libras_disponibles": round(disp_g / 500.0, 1), "gramos_disponibles": disp_g})

    total = sum(dict_compras.values()) + sum(dict_ajustes.values()) - sum(dict_usados.values())
    return {
        "inventario_disponible_g": max(0.0, total),
        "costo_promedio_gramo": (total_inversion_real / total_comprado_real) if total_comprado_real > 0 else 0.0,
        "productos_stock": tarjetas,
    }


# ---------------- Venta: stock y costo ----------------

def evaluar_stock(items, resumen_cafe=None, resumen_emp=None):
    """Devuelve (alcanza, faltantes) para un conjunto de ítems."""
    resumen_cafe = resumen_cafe or resumen_inventario()
    resumen_emp = resumen_emp or resumen_empaques()
    faltantes = {}
    total_g = sum(int(i.get("gramos_totales", 0)) for i in items)
    if total_g > resumen_cafe["inventario_disponible_g"]:
        faltantes["cafe_g"] = total_g - resumen_cafe["inventario_disponible_g"]
    for k, req in empaques_requeridos(items).items():
        if req > resumen_emp[k]["disponibles"]:
            faltantes[k] = req - resumen_emp[k]["disponibles"]
    return (not faltantes), faltantes


def costo_estimado(items, resumen_cafe, resumen_emp) -> int:
    productos = list(db.productos.find({}, {"nombre": 1, "costo_por_libra": 1}))
    por_id = {str(p["_id"]): p for p in productos}
    por_nombre = {p["nombre"]: p for p in productos}

    costo_cafe = 0.0
    for it in items:
        prod = por_id.get(str(it.get("producto_id") or "")) or por_nombre.get(it.get("nombre"))
        costo_libra = (prod or {}).get("costo_por_libra", 0.0) or 0.0
        costo_gramo = (costo_libra / 500.0) if costo_libra > 0 else resumen_cafe["costo_promedio_gramo"]
        costo_cafe += int(it.get("gramos_totales", 0)) * costo_gramo

    costo_emp = 0.0
    for k, cant in empaques_requeridos(items).items():
        costo_emp += cant * resumen_emp[k]["costo_unitario"]
    return round(costo_cafe + costo_emp)


def limpiar_items(items) -> list:
    """Recalcula gramos y subtotales en el servidor: no se confía en los del navegador."""
    limpios = []
    for it in items:
        d = it.model_dump()
        precio = max(0.0, float(d.get("precio_unitario") or 0.0))
        desc = min(precio, max(0.0, float(d.get("descuento") or 0.0)))
        d["precio_unitario"] = precio
        d["descuento"] = desc
        d["gramos_totales"] = int(d["gramaje"]) * int(d["cantidad"])
        d["subtotal"] = max(0.0, (precio - desc) * d["cantidad"])
        limpios.append(d)
    return limpios


def normalizar_pago(tipo_pago: str, es_obsequio: bool) -> str:
    if es_obsequio:
        return "N/A"
    tipo = tipo_pago or "Contado"
    return "Contado" if tipo == "Efectivo" else tipo


def siguiente_consecutivo(tipo_contador="factura_num") -> str:
    ret = db.contadores.find_one_and_update(
        {"_id": tipo_contador}, {"$inc": {"seq": 1}}, upsert=True, return_document=True
    )
    num = ret.get("seq", 1)
    if num > 5000:
        num = ((num - 1) % 5000) + 1
    return f"{num:04d}"


def ahora():
    return datetime.utcnow()
