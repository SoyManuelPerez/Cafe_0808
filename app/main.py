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
from app.models import (
    CompraCreate, CompraEmpaqueCreate, ProductoCreate, ProductoUpdate, 
    ClienteCreate, VentaCreate, UserLogin, UserCreate, UserUpdate
)
from app.pdf_generator import generar_factura_pdf

app = FastAPI(title="0808 Café de Especialidad")

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

db = get_db()

# ==========================================
# FUNCIONES DE SEGURIDAD Y ROLES
# ==========================================

def hash_password(password: str) -> str:
    pwd_bytes = password.strip().encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.strip().encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

try:
    admin_existente = db.usuarios.find_one({"username": "admin"})
    if not admin_existente:
        hashed_default = hash_password("0808cafe")
        db.usuarios.insert_one({
            "username": "admin",
            "password_hash": hashed_default,
            "rol": "admin",
            "creado_en": datetime.utcnow()
        })
    else:
        db.usuarios.update_one({"username": "admin"}, {"$set": {"rol": "admin"}})
except Exception as e:
    print(f"Error verificando usuario admin inicial: {e}")

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
# RUTAS AUTENTICACIÓN Y VISTAS
# ==========================================

@app.post("/api/login")
def login(user_data: UserLogin, response: Response):
    username_clean = user_data.username.strip()
    user = db.usuarios.find_one({"username": username_clean})

    if not user or not verify_password(user_data.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    
    rol = user.get("rol", "ventas")
    response.set_cookie(key="session_user", value=username_clean, httponly=True)
    return {"mensaje": "Login exitoso", "username": username_clean, "rol": rol}

@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("session_user")
    return {"mensaje": "Sesión cerrada"}

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

# ==========================================
# ENDPOINTS GESTIÓN DE USUARIOS
# ==========================================

@app.post("/api/usuarios", status_code=201)
def crear_usuario(usr: UserCreate):
    usuario_existente = db.usuarios.find_one({"username": usr.username.strip()})
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe.")
    
    hashed = hash_password(usr.password)
    doc = {
        "username": usr.username.strip(),
        "password_hash": hashed,
        "rol": usr.rol if usr.rol in ["admin", "ventas"] else "ventas",
        "creado_en": datetime.utcnow()
    }
    res = db.usuarios.insert_one(doc)
    return {"id": str(res.inserted_id), "mensaje": "Usuario creado exitosamente"}

@app.get("/api/usuarios")
def listar_usuarios():
    usuarios = list(db.usuarios.find({}, {"password_hash": 0}).sort("username", 1))
    return [fix_id(u) for u in usuarios]

@app.put("/api/usuarios/{user_id}")
def editar_usuario(user_id: str, usr: UserUpdate):
    usr_name = usr.username.strip()
    existente = db.usuarios.find_one({"username": usr_name, "_id": {"$ne": ObjectId(user_id)}})
    if existente:
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está en uso.")

    update_fields = {"username": usr_name}
    if usr.password and usr.password.strip():
        update_fields["password_hash"] = hash_password(usr.password)
    if usr.rol and usr.rol in ["admin", "ventas"]:
        update_fields["rol"] = usr.rol

    res = db.usuarios.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_fields}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"mensaje": "Usuario actualizado exitosamente"}

@app.delete("/api/usuarios/{user_id}")
def eliminar_usuario(user_id: str):
    user_to_delete = db.usuarios.find_one({"_id": ObjectId(user_id)})
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user_to_delete.get("username") == "admin":
        raise HTTPException(status_code=400, detail="No se puede eliminar el usuario administrador principal ('admin').")

    db.usuarios.delete_one({"_id": ObjectId(user_id)})
    return {"mensaje": "Usuario eliminado correctamente"}

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

    ventas = list(db.ventas.find({"estado_despacho": {"$ne": "Pendiente"}}))
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
        
        ajuste = db.ajustes_empaques.find_one({"tipo_empaque": t})
        if ajuste:
            disponibles = ajuste.get("disponibles", 0)
            costo_unitario = ajuste.get("costo_unitario", 0.0)
        else:
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

    db.ajustes_empaques.update_one(
        {"tipo_empaque": tipo_empaque},
        {"$set": {"disponibles": disponibles_deseados, "costo_unitario": nuevo_costo_unitario}},
        upsert=True
    )

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
        try:
            prod = db.productos.find_one({"_id": ObjectId(compra.producto_id)})
            if prod:
                nombre_producto = prod["nombre"]
                db.productos.update_many(
                    {"nombre": prod["nombre"]},
                    {"$set": {"costo_por_libra": costo_por_libra}}
                )
        except Exception:
            pass

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
        {"$match": {"estado_despacho": {"$ne": "Pendiente"}}},
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
        
        disp_g = max(0.0, comprado_g - usado_g)

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
# ENDPOINTS ENVÍOS CONSOLIDADOS
# ==========================================

@app.get("/api/envios")
def listar_envios():
    envios = list(db.envios.find().sort("fecha", -1))
    return [fix_id(e) for e in envios]

@app.post("/api/envios", status_code=201)
def crear_envio(data: dict):
    doc = {
        "fecha": data.get("fecha"),
        "nota": data.get("nota"),
        "valor_envio": float(data.get("valor_envio", 0.0)),
        "items": data.get("items", []),
        "facturas_ids": [],
        "creado_en": datetime.utcnow()
    }
    res = db.envios.insert_one(doc)
    return {"id": str(res.inserted_id), "mensaje": "Envío registrado"}

@app.put("/api/envios/{envio_id}/asociar-facturas")
def asociar_facturas_envio(envio_id: str, data: dict):
    facturas_ids = data.get("facturas_ids", [])
    res = db.envios.update_one(
        {"_id": ObjectId(envio_id)},
        {"$set": {"facturas_ids": facturas_ids}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    return {"mensaje": "Facturas asociadas correctamente"}

@app.delete("/api/envios/{envio_id}")
def eliminar_envio(envio_id: str):
    res = db.envios.delete_one({"_id": ObjectId(envio_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    return {"mensaje": "Envío eliminado"}

# ==========================================
# ENDPOINTS VENTAS Y VENTAS PARCIALES
# ==========================================

@app.post("/api/ventas", status_code=201)
def registrar_venta(venta: VentaCreate, request: Request):
    vendedor = venta.vendedor or request.cookies.get("session_user", "admin")
    resumen_cafe = resumen_inventario()
    resumen_emp = resumen_empaques()

    es_obsequio = (venta.tipo_venta == "Obsequio")
    total_venta = 0.0 if es_obsequio else sum(i.subtotal for i in venta.items)
    total_gramos = sum(i.gramos_totales for i in venta.items)
    
    stock_insuficiente = False
    motivo_faltante = {}

    if total_gramos > resumen_cafe["inventario_disponible_g"]:
        stock_insuficiente = True
        motivo_faltante["cafe_g"] = total_gramos - resumen_cafe["inventario_disponible_g"]

    req_empaques = {"bolsa_250g": 0, "bolsa_500g": 0, "etiqueta_250g": 0, "etiqueta_500g": 0}
    for item in venta.items:
        cant = item.cantidad
        g = item.gramaje
        if g == 250:
            req_empaques["bolsa_250g"] += cant
            req_empaques["etiqueta_250g"] += cant
        elif g == 500:
            req_empaques["bolsa_500g"] += cant
            req_empaques["etiqueta_500g"] += cant

    for k, v_req in req_empaques.items():
        if v_req > resumen_emp[k]["disponibles"]:
            stock_insuficiente = True
            motivo_faltante[k] = v_req - resumen_emp[k]["disponibles"]

    estado_despacho = "Pendiente" if stock_insuficiente else "Completo"

    costo_cafe = total_gramos * resumen_cafe["costo_promedio_gramo"]
    
    costo_empaques_total = 0.0
    for item in venta.items:
        cant = item.cantidad
        g = item.gramaje
        if g == 250:
            costo_empaques_total += cant * (resumen_emp["bolsa_250g"]["costo_unitario"] + resumen_emp["etiqueta_250g"]["costo_unitario"])
        elif g == 500:
            costo_empaques_total += cant * (resumen_emp["bolsa_500g"]["costo_unitario"] + resumen_emp["etiqueta_500g"]["costo_unitario"])

    costo_est = round(costo_cafe + costo_empaques_total)
    consecutivo = obtener_siguiente_consecutivo("factura_num")

    tipo_pago_final = "N/A" if es_obsequio else (venta.tipo_pago if venta.tipo_pago else "Contado")
    if tipo_pago_final == "Efectivo":
        tipo_pago_final = "Contado"

    doc = {
        "consecutivo_str": consecutivo,
        "fecha": venta.fecha,
        "cliente": venta.cliente,
        "vendedor": vendedor,
        "tipo_pago": tipo_pago_final,
        "tipo_venta": venta.tipo_venta,
        "estado_despacho": estado_despacho,
        "faltantes": motivo_faltante if stock_insuficiente else {},
        "estado_credito": "Pendiente" if (tipo_pago_final == "Crédito" and not es_obsequio) else "N/A",
        "total_venta": total_venta,
        "costo_estimado": costo_est,
        "ganancia": total_venta - costo_est,
        "items": [i.model_dump() if hasattr(i, "model_dump") else i.dict() for i in venta.items],
        "creado_en": datetime.utcnow()
    }
    res = db.ventas.insert_one(doc)
    return {"id": str(res.inserted_id), "consecutivo": consecutivo, "estado_despacho": estado_despacho}

@app.get("/api/ventas")
def listar_ventas():
    ventas = list(db.ventas.find().sort("fecha", -1))
    envios = list(db.envios.find())

    fletes_por_factura = {}
    for env in envios:
        facturas = env.get("facturas_ids", [])
        num_facturas = len(facturas)
        if num_facturas > 0:
            flete_unitario = env.get("valor_envio", 0.0) / num_facturas
            for f_id in facturas:
                fletes_por_factura[str(f_id)] = fletes_por_factura.get(str(f_id), 0.0) + flete_unitario

    ventas_formateadas = []
    for v in ventas:
        v_clean = fix_id(v)
        v_id = str(v_clean.get("id", ""))
        
        if v_clean.get("tipo_pago") == "Efectivo":
            v_clean["tipo_pago"] = "Contado"

        flete_aplicado = fletes_por_factura.get(v_id, 0.0)
        v_clean["costo_envio_asociado"] = flete_aplicado
        
        ganancia_base = float(v_clean.get("ganancia", 0.0))
        v_clean["ganancia"] = ganancia_base - flete_aplicado
        
        ventas_formateadas.append(v_clean)

    return ventas_formateadas

@app.put("/api/ventas/{venta_id}/completar-despacho")
def completar_despacho_venta(venta_id: str):
    venta = db.ventas.find_one({"_id": ObjectId(venta_id)})
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    if venta.get("estado_despacho") == "Completo":
        return {"mensaje": "La venta ya está completada"}

    resumen_cafe = resumen_inventario()
    resumen_emp = resumen_empaques()

    total_gramos = sum(i.get("gramos_totales", 0) for i in venta.get("items", []))
    if total_gramos > resumen_cafe["inventario_disponible_g"]:
        raise HTTPException(status_code=400, detail="Inventario de café todavía insuficiente para completar el despacho.")

    req_empaques = {"bolsa_250g": 0, "bolsa_500g": 0, "etiqueta_250g": 0, "etiqueta_500g": 0}
    for item in venta.get("items", []):
        cant = item.get("cantidad", 0)
        g = item.get("gramaje", 0)
        if g == 250:
            req_empaques["bolsa_250g"] += cant
            req_empaques["etiqueta_250g"] += cant
        elif g == 500:
            req_empaques["bolsa_500g"] += cant
            req_empaques["etiqueta_500g"] += cant

    for k, v_req in req_empaques.items():
        if v_req > resumen_emp[k]["disponibles"]:
            nombre_legible = k.replace('_', ' ').title()
            raise HTTPException(status_code=400, detail=f"Stock insuficiente de {nombre_legible} para completar.")

    db.ventas.update_one(
        {"_id": ObjectId(venta_id)},
        {"$set": {"estado_despacho": "Completo", "faltantes": {}}}
    )
    return {"mensaje": "Venta completada y stock descontado exitosamente"}

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
# ENDPOINTS COTIZACIONES
# ==========================================

@app.post("/api/cotizaciones", status_code=201)
def registrar_cotizacion(cotizacion: VentaCreate, request: Request):
    vendedor = cotizacion.vendedor or request.cookies.get("session_user", "admin")
    total_cotizacion = sum(i.subtotal for i in cotizacion.items)
    consecutivo = obtener_siguiente_consecutivo("cotizacion_num")

    tipo_pago_cot = cotizacion.tipo_pago if cotizacion.tipo_pago else "Contado"
    if tipo_pago_cot == "Efectivo":
        tipo_pago_cot = "Contado"

    doc = {
        "consecutivo_str": consecutivo,
        "fecha": cotizacion.fecha,
        "cliente": cotizacion.cliente,
        "vendedor": vendedor,
        "tipo_pago": tipo_pago_cot,
        "total_venta": total_cotizacion,
        "items": [i.model_dump() if hasattr(i, "model_dump") else i.dict() for i in cotizacion.items],
        "creado_en": datetime.utcnow()
    }
    res = db.cotizaciones.insert_one(doc)
    return {"id": str(res.inserted_id), "consecutivo": consecutivo}

@app.get("/api/cotizaciones")
def listar_cotizaciones():
    cotizaciones = list(db.cotizaciones.find().sort("fecha", -1))
    cotizaciones_clean = []
    for c in cotizaciones:
        c_item = fix_id(c)
        if c_item.get("tipo_pago") == "Efectivo":
            c_item["tipo_pago"] = "Contado"
        cotizaciones_clean.append(c_item)
    return cotizaciones_clean

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

# ==========================================
# ENDPOINT PARA EDITAR VENTA (CLIENTE Y PAGO)
# ==========================================

@app.put("/api/ventas/{venta_id}/editar-detalles")
def editar_detalles_venta(venta_id: str, data: dict):
    nuevo_cliente = data.get("cliente")
    nuevo_tipo_pago = data.get("tipo_pago")

    if not nuevo_cliente or not nuevo_tipo_pago:
        raise HTTPException(status_code=400, detail="El cliente y el tipo de pago son obligatorios.")

    venta = db.ventas.find_one({"_id": ObjectId(venta_id)})
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    es_obsequio = (venta.get("tipo_venta") == "Obsequio")
    
    # Ajustar estado del crédito según el nuevo tipo de pago
    if es_obsequio:
        tipo_pago_final = "N/A"
        estado_credito_final = "N/A"
    else:
        tipo_pago_final = nuevo_tipo_pago
        if tipo_pago_final == "Crédito":
            # Si cambia a crédito y no tenía estado asignado, pasa a Pendiente
            estado_credito_final = venta.get("estado_credito") if venta.get("estado_credito") in ["Pendiente", "Pagado"] else "Pendiente"
        else:
            estado_credito_final = "N/A"

    db.ventas.update_one(
        {"_id": ObjectId(venta_id)},
        {"$set": {
            "cliente": nuevo_cliente,
            "tipo_pago": tipo_pago_final,
            "estado_credito": estado_credito_final
        }}
    )

    return {"mensaje": "Venta actualizada correctamente"}
