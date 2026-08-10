import os
import sys
import bcrypt
from datetime import datetime
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.database import get_db, fix_id
from app.models import CompraCreate, CompraEmpaqueCreate, ProductoCreate, ProductoUpdate, ClienteCreate, VentaCreate, UserLogin
from app.pdf_generator import generar_factura_pdf

app = FastAPI(title="0808 Café de Especialidad")

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

db = get_db()

# ==========================================
# FUNCIONES DE SEGURIDAD (BCRYPT NATIVO)
# ==========================================

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

user_admin = db.usuarios.find_one({"username": "admin"})
if not user_admin:
    hashed_default = hash_password("0808cafe")
    db.usuarios.insert_one({"username": "admin", "password_hash": hashed_default})
else:
    if not verify_password("0808cafe", user_admin.get("password_hash", "")):
        hashed_updated = hash_password("0808cafe")
        db.usuarios.update_one({"username": "admin"}, {"$set": {"password_hash": hashed_updated}})

def obtener_siguiente_consecutivo(tipo_contador="factura_num"):
    ret = db.contadores.find_one_and_update(
        {"_id": tipo_contador},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    num_seq = ret.get("seq", 1)
    if num_seq > 5000:
        num_seq = ((num_seq - 1) % 5000) + 1
    return f"{num_seq:04d}"

# ==========================================
# RUTAS AUTENTICACIÓN
# ==========================================

@app.post("/api/login")
def login(user_data: UserLogin, response: Response):
    user = db.usuarios.find_one({"username": user_data.username})
    if not user or not verify_password(user_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    
    response.set_cookie(key="session_user", value=user_data.username, httponly=True)
    return {"mensaje": "Login exitoso"}

@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("session_user")
    return {"mensaje": "Sesión cerrada"}

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

# ==========================================
# ENDPOINTS CLIENTES
# ==========================================

@app.post("/api/clientes", status_code=201)
def crear_cliente(cli: ClienteCreate):
    doc = cli.model_dump() if hasattr(cli, "model_dump") else cli.dict()
    doc["creado_en"] = datetime.utcnow()
    res = db.clientes.insert_one(doc)
    return {"id": str(res.inserted_id)}

@app.get("/api/clientes")
def listar_clientes():
    clientes = list(db.clientes.find().sort("nombre", 1))
    return [fix_id(c) for c in clientes]

@app.put("/api/clientes/{cliente_id}")
def editar_cliente(cliente_id: str, cli: ClienteCreate):
    res = db.clientes.update_one(
        {"_id": ObjectId(cliente_id)},
        {"$set": {"nombre": cli.nombre, "celular": cli.celular}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"mensaje": "Cliente actualizado exitosamente"}

@app.delete("/api/clientes/{cliente_id}")
def eliminar_cliente(cliente_id: str):
    res = db.clientes.delete_one({"_id": ObjectId(cliente_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"mensaje": "Cliente eliminado"}

# ==========================================
# ENDPOINTS COMPRAS DE EMPAQUES
# ==========================================

@app.post("/api/compras-empaques", status_code=201)
def crear_compra_empaque(compra: CompraEmpaqueCreate):
    costo_unitario = (compra.costo_total / compra.cantidad) if compra.cantidad > 0 else 0.0
    doc = {
        "fecha": compra.fecha,
        "tipo_empaque": compra.tipo_empaque,
        "cantidad": compra.cantidad,
        "costo_total": compra.costo_total,
        "costo_unitario": costo_unitario,
        "creado_en": datetime.utcnow()
    }
    res = db.compras_empaques.insert_one(doc)
    return {"id": str(res.inserted_id)}

@app.get("/api/compras-empaques")
def listar_compras_empaques():
    compras = list(db.compras_empaques.find().sort("fecha", -1))
    return [fix_id(c) for c in compras]

@app.get("/api/empaques/resumen")
def resumen_empaques():
    tipos = ["bolsa_250g", "bolsa_500g", "etiqueta_250g", "etiqueta_500g"]
    
    compras_agrupadas = list(db.compras_empaques.aggregate([
        {"$group": {
            "_id": "$tipo_empaque",
            "total_cant": {"$sum": "$cantidad"},
            "total_costo": {"$sum": "$costo_total"}
        }}
    ]))
    dict_compras = {c["_id"]: c for c in compras_agrupadas}

    ventas = list(db.ventas.find())
    usados = {
        "bolsa_250g": 0,
        "bolsa_500g": 0,
        "etiqueta_250g": 0,
        "etiqueta_500g": 0
    }

    for v in ventas:
        for item in v.get("items", []):
            cant = item.get("cantidad", 0)
            gramaje = item.get("gramaje", 0)
            if gramaje == 250:
                usados["bolsa_250g"] += cant
                usados["etiqueta_250g"] += cant
            elif gramaje == 500:
                usados["bolsa_500g"] += cant
                usados["etiqueta_500g"] += cant

    resumen = {}
    for t in tipos:
        compra_info = dict_compras.get(t, {"total_cant": 0, "total_costo": 0.0})
        total_cant = compra_info["total_cant"]
        total_costo = compra_info["total_costo"]
        cant_usada = usados.get(t, 0)
        disponibles = max(0, total_cant - cant_usada)
        costo_unitario = (total_costo / total_cant) if total_cant > 0 else 0.0

        resumen[t] = {
            "comprados": total_cant,
            "usados": cant_usada,
            "disponibles": disponibles,
            "costo_unitario": round(costo_unitario, 2)
        }

    return resumen

@app.put("/api/empaques/ajuste-manual")
def ajustar_empaque_manual(data: dict):
    tipo_empaque = data.get("tipo_empaque")
    disponibles_deseados = int(data.get("disponibles", 0))
    nuevo_costo_unitario = float(data.get("costo_unitario", 0.0))

    if not tipo_empaque:
        raise HTTPException(status_code=400, detail="Tipo de empaque requerido")

    ventas = list(db.ventas.find())
    usados = 0
    for v in ventas:
        for item in v.get("items", []):
            cant = item.get("cantidad", 0)
            gramaje = item.get("gramaje", 0)
            if "250g" in tipo_empaque and gramaje == 250:
                usados += cant
            elif "500g" in tipo_empaque and gramaje == 500:
                usados += cant

    nueva_cantidad_total = disponibles_deseados + usados
    nuevo_costo_total = nueva_cantidad_total * nuevo_costo_unitario

    db.compras_empaques.delete_many({"tipo_empaque": tipo_empaque})
    if nueva_cantidad_total > 0:
        db.compras_empaques.insert_one({
            "fecha": datetime.utcnow().strftime("%Y-%m-%d"),
            "tipo_empaque": tipo_empaque,
            "cantidad": nueva_cantidad_total,
            "costo_total": nuevo_costo_total,
            "costo_unitario": nuevo_costo_unitario,
            "creado_en": datetime.utcnow()
        })

    return {"mensaje": f"Empaque {tipo_empaque} actualizado correctamente"}

# ==========================================
# ENDPOINTS PRODUCTOS & COMPRAS
# ==========================================

@app.get("/api/productos/unicos")
def listar_productos_unicos():
    pipeline = [
        {"$group": {
            "_id": "$nombre",
            "id": {"$first": {"$toString": "$_id"}},
            "nombre": {"$first": "$nombre"},
            "costo_por_libra": {"$first": "$costo_por_libra"}
        }}
    ]
    unicos = list(db.productos.aggregate(pipeline))
    return unicos

@app.put("/api/productos/actualizar-costo-libra")
def actualizar_costo_libra_manual(data: dict):
    nombre = data.get("nombre")
    costo_por_libra = float(data.get("costo_por_libra", 0))
    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre requerido")
    
    db.productos.update_many(
        {"nombre": nombre},
        {"$set": {"costo_por_libra": costo_por_libra}}
    )
    return {"mensaje": "Costo por libra actualizado"}

@app.post("/api/compras", status_code=201)
def crear_compra(compra: CompraCreate):
    gramos = compra.libras * 500.0
    costo_por_gramo = (compra.costo_total / gramos) if gramos > 0 else 0.0
    costo_por_libra = (compra.costo_total / compra.libras) if compra.libras > 0 else 0.0

    nombre_producto = "Materia Prima General"
    if compra.producto_id:
        prod = db.productos.find_one({"_id": ObjectId(compra.producto_id)})
        if prod:
            nombre_producto = prod["nombre"]
            db.productos.update_many(
                {"nombre": prod["nombre"]},
                {"$set": {"costo_por_libra": costo_por_libra}}
            )

    doc = {
        "fecha": compra.fecha,
        "libras": compra.libras,
        "gramos": gramos,
        "costo_total": compra.costo_total,
        "costo_por_gramo": costo_por_gramo,
        "costo_por_libra": costo_por_libra,
        "producto_id": compra.producto_id,
        "producto_nombre": nombre_producto,
        "creado_en": datetime.utcnow()
    }
    res = db.compras.insert_one(doc)
    return {"id": str(res.inserted_id)}

@app.get("/api/compras")
def listar_compras():
    compras = list(db.compras.find().sort("fecha", -1))
    prods_map = {str(p["_id"]): p["nombre"] for p in db.productos.find()}
    
    for c in compras:
        if "producto_nombre" not in c or not c["producto_nombre"]:
            p_id = str(c.get("producto_id", ""))
            c["producto_nombre"] = prods_map.get(p_id, "Materia Prima General")

    return [fix_id(c) for c in compras]

@app.post("/api/productos", status_code=201)
def crear_producto(prod: ProductoCreate):
    doc = prod.model_dump() if hasattr(prod, "model_dump") else prod.dict()
    doc["creado_en"] = datetime.utcnow()
    if "costo_por_libra" not in doc or doc["costo_por_libra"] is None:
        doc["costo_por_libra"] = 0.0
    res = db.productos.insert_one(doc)
    return {"id": str(res.inserted_id)}

@app.get("/api/productos")
def listar_productos():
    prods = list(db.productos.find())
    return [fix_id(p) for p in prods]

@app.put("/api/productos/{prod_id}")
def editar_producto(prod_id: str, prod: ProductoUpdate):
    res = db.productos.update_one(
        {"_id": ObjectId(prod_id)},
        {"$set": {"nombre": prod.nombre, "precio_venta": prod.precio_venta}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"mensaje": "Producto actualizado"}

@app.delete("/api/productos/{prod_id}")
def eliminar_producto(prod_id: str):
    usos = db.ventas.count_documents({"items.producto_id": prod_id})
    if usos > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar: el producto tiene ventas asociadas.")
    db.productos.delete_one({"_id": ObjectId(prod_id)})
    return {"mensaje": "Producto eliminado exitosamente"}

@app.get("/api/inventario/resumen")
def resumen_inventario():
    compras_agrupadas = list(db.compras.aggregate([
        {"$group": {
            "_id": "$producto_nombre",
            "total_g": {"$sum": "$gramos"},
            "total_costo": {"$sum": "$costo_total"}
        }}
    ]))
    
    total_comprado_general = sum(c["total_g"] for c in compras_agrupadas)
    total_inversion_general = sum(c["total_costo"] for c in compras_agrupadas)
    dict_compras_nombre = {c["_id"]: c["total_g"] for c in compras_agrupadas if c["_id"]}

    ventas_agrupadas = list(db.ventas.aggregate([
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.nombre",
            "usados_g": {"$sum": "$items.gramos_totales"}
        }}
    ]))
    
    dict_usados_nombre = {v["_id"]: v["usados_g"] for v in ventas_agrupadas if v["_id"]}
    total_usado_general = sum(dict_usados_nombre.values())

    productos = list(db.productos.find())
    nombres_unicos = list(set([p["nombre"] for p in productos]))

    resumen_tarjetas = []
    for nombre in nombres_unicos:
        comprado_g = dict_compras_nombre.get(nombre, 0.0)
        usado_g = dict_usados_nombre.get(nombre, 0.0)
        
        if comprado_g > 0:
            disp_g = max(0.0, comprado_g - usado_g)
        elif nombre in dict_compras_nombre:
            disp_g = max(0.0, dict_compras_nombre[nombre] - usado_g)
        else:
            disp_g = 0.0

        resumen_tarjetas.append({
            "nombre": nombre,
            "libras_disponibles": round(disp_g / 500.0, 1)
        })

    return {
        "inventario_disponible_g": max(0.0, total_comprado_general - total_usado_general),
        "costo_promedio_gramo": (total_inversion_general / total_comprado_general) if total_comprado_general > 0 else 0.0,
        "productos_stock": resumen_tarjetas
    }

# ==========================================
# ENDPOINTS VENTAS
# ==========================================

@app.post("/api/ventas", status_code=201)
def registrar_venta(venta: VentaCreate):
    resumen_cafe = resumen_inventario()
    resumen_emp = resumen_empaques()

    es_obsequio = (venta.tipo_venta == "Obsequio")
    total_venta = 0.0 if es_obsequio else sum(i.subtotal for i in venta.items)
    total_gramos = sum(i.gramos_totales for i in venta.items)
    
    if total_gramos > resumen_cafe["inventario_disponible_g"]:
        raise HTTPException(status_code=400, detail="Inventario de café insuficiente para procesar la venta.")

    req_empaques = {"bolsa_250g": 0, "bolsa_500g": 0, "etiqueta_250g": 0, "etiqueta_500g": 0}
    costo_empaques_total = 0.0

    for item in venta.items:
        cant = item.cantidad
        g = item.gramaje
        if g == 250:
            req_empaques["bolsa_250g"] += cant
            req_empaques["etiqueta_250g"] += cant
            costo_empaques_total += cant * (resumen_emp["bolsa_250g"]["costo_unitario"] + resumen_emp["etiqueta_250g"]["costo_unitario"])
        elif g == 500:
            req_empaques["bolsa_500g"] += cant
            req_empaques["etiqueta_500g"] += cant
            costo_empaques_total += cant * (resumen_emp["bolsa_500g"]["costo_unitario"] + resumen_emp["etiqueta_500g"]["costo_unitario"])

    for k, v_req in req_empaques.items():
        if v_req > resumen_emp[k]["disponibles"]:
            nombre_legible = k.replace('_', ' ').title()
            raise HTTPException(status_code=400, detail=f"Inventario insuficiente de empaque: {nombre_legible}. Requeridos: {v_req}, Disponibles: {resumen_emp[k]['disponibles']}")

    costo_cafe = total_gramos * resumen_cafe["costo_promedio_gramo"]
    costo_est = round(costo_cafe + costo_empaques_total)
    consecutivo = obtener_siguiente_consecutivo("factura_num")

    doc = {
        "consecutivo_str": consecutivo,
        "fecha": venta.fecha,
        "cliente": venta.cliente,
        "tipo_pago": "N/A" if es_obsequio else venta.tipo_pago,
        "tipo_venta": venta.tipo_venta,
        "estado_credito": "Pendiente" if (venta.tipo_pago == "Crédito" and not es_obsequio) else "N/A",
        "total_venta": total_venta,
        "costo_estimado": costo_est,
        "ganancia": total_venta - costo_est,
        "items": [i.model_dump() if hasattr(i, "model_dump") else i.dict() for i in venta.items],
        "creado_en": datetime.utcnow()
    }
    res = db.ventas.insert_one(doc)
    return {"id": str(res.inserted_id), "consecutivo": consecutivo}

@app.get("/api/ventas")
def listar_ventas():
    ventas = list(db.ventas.find().sort("fecha", -1))
    return [fix_id(v) for v in ventas]

@app.put("/api/ventas/{venta_id}/pagar-credito")
def pagar_credito(venta_id: str):
    res = db.ventas.update_one({"_id": ObjectId(venta_id)}, {"$set": {"estado_credito": "Pagado"}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return {"mensaje": "Crédito pagado"}

@app.delete("/api/ventas/{venta_id}")
def eliminar_venta(venta_id: str):
    res = db.ventas.delete_one({"_id": ObjectId(venta_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return {"mensaje": "Venta eliminada correctamente"}

@app.get("/api/ventas/{venta_id}/pdf")
def descargar_factura(venta_id: str):
    venta = db.ventas.find_one({"_id": ObjectId(venta_id)})
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    pdf_bytes = generar_factura_pdf(venta, venta["items"], es_cotizacion=False)
    num_factura = venta.get("consecutivo_str", str(venta_id)[:8])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=Factura_{num_factura}.pdf"
        }
    )

# ==========================================
# ENDPOINTS COTIZACIONES (SIN DESCONTAR STOCK)
# ==========================================

@app.post("/api/cotizaciones", status_code=201)
def registrar_cotizacion(cotizacion: VentaCreate):
    total_cotizacion = sum(i.subtotal for i in cotizacion.items)
    consecutivo = obtener_siguiente_consecutivo("cotizacion_num")

    doc = {
        "consecutivo_str": consecutivo,
        "fecha": cotizacion.fecha,
        "cliente": cotizacion.cliente,
        "tipo_pago": cotizacion.tipo_pago,
        "total_venta": total_cotizacion,
        "items": [i.model_dump() if hasattr(i, "model_dump") else i.dict() for i in cotizacion.items],
        "creado_en": datetime.utcnow()
    }
    res = db.cotizaciones.insert_one(doc)
    return {"id": str(res.inserted_id), "consecutivo": consecutivo}

@app.get("/api/cotizaciones")
def listar_cotizaciones():
    cotizaciones = list(db.cotizaciones.find().sort("fecha", -1))
    return [fix_id(c) for c in cotizaciones]

@app.get("/api/cotizaciones/{cotizacion_id}/pdf")
def descargar_cotizacion_pdf(cotizacion_id: str):
    cotizacion = db.cotizaciones.find_one({"_id": ObjectId(cotizacion_id)})
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    pdf_bytes = generar_factura_pdf(cotizacion, cotizacion["items"], es_cotizacion=True)
    num_cot = cotizacion.get("consecutivo_str", str(cotizacion_id)[:8])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=Cotizacion_{num_cot}.pdf"
        }
    )

@app.delete("/api/cotizaciones/{cotizacion_id}")
def eliminar_cotizacion(cotizacion_id: str):
    res = db.cotizaciones.delete_one({"_id": ObjectId(cotizacion_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    return {"mensaje": "Cotización eliminada correctamente"}
