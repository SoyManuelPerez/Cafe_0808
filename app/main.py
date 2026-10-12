import os
import sys
import bcrypt
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.database import get_db, fix_id
from app.models import (
    CompraCreate, CompraEmpaqueCreate, ProductoCreate, ProductoUpdate, 
    ClienteCreate, VentaCreate, UserLogin, UserCreate, UserUpdate,
    AjusteInventarioCreate
)
from app.pdf_generator import generar_factura_pdf

# ==========================================
# MODELO PYDANTIC PARA OTROS GASTOS
# ==========================================
class GastoCreate(BaseModel):
    monto: float
    fecha: str
    observacion: str

app = FastAPI(title="0808 Café de Especialidad")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# ENDPOINT DE REPORTE RESUMEN DE VENTAS
# ==========================================

@app.get("/api/reportes/resumen-ventas")
def obtener_resumen_ventas():
    pipeline_agregacion = [
        {"$match": {"tipo_venta": {"$ne": "Anulado"}, "estado_despacho": {"$ne": "Anulado"}}},
        {
            "$group": {
                "_id": None,
                "total_ingresos": {"$sum": "$total_venta"},
                "total_ganancias": {"$sum": "$ganancia"},
                "cantidad_ventas": {"$sum": 1}
            }
        }
    ]
    resultado = list(db.ventas.aggregate(pipeline_agregacion))
    if not resultado:
        return {"total_ingresos": 0.0, "total_ganancias": 0.0, "cantidad_ventas": 0}
    
    res = resultado[0]
    res.pop("_id", None)
    return res

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
    celular_clean = cli.celular.strip() if cli.celular else ""
    
    if celular_clean:
        cliente_existente = db.clientes.find_one({"celular": celular_clean})
        if cliente_existente:
            nombre_existente = cliente_existente.get("nombre", "Desconocido")
            raise HTTPException(
                status_code=400, 
                detail=f"⚠️ El número de teléfono {celular_clean} ya pertenece al cliente: '{nombre_existente}'."
            )

    doc = cli.model_dump() if hasattr(cli, "model_dump") else cli.dict()
    doc["nombre"] = cli.nombre.strip()
    doc["celular"] = celular_clean
    doc["creado_en"] = datetime.utcnow()
    
    res = db.clientes.insert_one(doc)
    return {"id": str(res.inserted_id), "nombre": doc["nombre"]}

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
# ENDPOINTS OTROS GASTOS
# ==========================================

@app.post("/api/gastos", status_code=201)
def crear_gasto(gasto: GastoCreate):
    if gasto.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto del gasto debe ser mayor a 0.")

    doc = {
        "monto": gasto.monto,
        "fecha": gasto.fecha,
        "observacion": gasto.observacion.strip(),
        "creado_en": datetime.utcnow()
    }
    res = db.gastos.insert_one(doc)
    return {"id": str(res.inserted_id), "mensaje": "Gasto registrado exitosamente"}

@app.get("/api/gastos")
def listar_gastos():
    gastos = list(db.gastos.find().sort("fecha", -1))
    return [fix_id(g) for g in gastos]

@app.delete("/api/gastos/{gasto_id}")
def eliminar_gasto(gasto_id: str):
    res = db.gastos.delete_one({"_id": ObjectId(gasto_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return {"mensaje": "Gasto eliminado correctamente"}

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

    ventas = list(db.ventas.find({"estado_despacho": {"$ne": "Pendiente"}, "tipo_venta": {"$ne": "Anulado"}}))
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
            elif gramaje == 2500:
                usados["etiqueta_500g"] += cant

    resumen = {}
    for t in tipos:
        compra_info = dict_compras.get(t, {"total_cant": 0, "total_costo": 0.0})
        total_cant = compra_info["total_cant"]
        cant_usada = usados.get(t, 0)
        
        ajuste = db.ajustes_empaques.find_one({"tipo_empaque": t})
        if ajuste:
            disponibles = ajuste.get("disponibles", 0)
            costo_unitario = ajuste.get("costo_unitario", 0.0)
        else:
            disponibles = max(0, total_cant - cant_usada)
            ultima_compra = db.compras_empaques.find_one(
                {"tipo_empaque": t},
                sort=[("fecha", -1), ("_id", -1)]
            )
            costo_unitario = float(ultima_compra.get("costo_unitario", 0.0)) if ultima_compra else 0.0

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
    # Se excluyen ajustes manuales antiguos (gramos negativos): no son compras reales
    compras = list(db.compras.find({"gramos": {"$gt": 0}}).sort("fecha", -1))
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

def gramos_ajustados_por_producto():
    """Suma de ajustes manuales (entradas +, salidas -) por nombre de café, en gramos.
    Los ajustes viven en su propia colección: NO son compras, por eso no afectan
    costos, inversión ni ganancias."""
    agrupados = db.ajustes_inventario.aggregate([
        {"$group": {"_id": "$producto_nombre", "total_g": {"$sum": "$gramos"}}}
    ])
    return {a["_id"]: a["total_g"] for a in agrupados if a["_id"]}

@app.get("/api/inventario/resumen")
def resumen_inventario():
    # Todas las compras (incluye ajustes antiguos guardados como compras negativas) -> solo para STOCK
    compras_agrupadas = list(db.compras.aggregate([
        {"$group": {
            "_id": "$producto_nombre",
            "total_g": {"$sum": "$gramos"}
        }}
    ]))
    dict_compras_nombre = {c["_id"]: c["total_g"] for c in compras_agrupadas if c["_id"]}

    # Solo compras reales (gramos > 0) -> para COSTO PROMEDIO. Así los descuentos manuales
    # antiguos (gramos negativos y costo 0) tampoco inflan el costo por gramo.
    compras_reales = list(db.compras.aggregate([
        {"$match": {"gramos": {"$gt": 0}}},
        {"$group": {
            "_id": None,
            "total_g": {"$sum": "$gramos"},
            "total_costo": {"$sum": "$costo_total"}
        }}
    ]))
    total_comprado_real = compras_reales[0]["total_g"] if compras_reales else 0.0
    total_inversion_real = compras_reales[0]["total_costo"] if compras_reales else 0.0

    dict_ajustes_nombre = gramos_ajustados_por_producto()
    total_ajustes_general = sum(dict_ajustes_nombre.values())
    total_comprado_general = sum(dict_compras_nombre.values())

    ventas_agrupadas = list(db.ventas.aggregate([
        {"$match": {"estado_despacho": {"$ne": "Pendiente"}, "tipo_venta": {"$ne": "Anulado"}}},
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
        ajustado_g = dict_ajustes_nombre.get(nombre, 0.0)
        usado_g = dict_usados_nombre.get(nombre, 0.0)

        disp_g = max(0.0, comprado_g + ajustado_g - usado_g)

        resumen_tarjetas.append({
            "nombre": nombre,
            "libras_disponibles": round(disp_g / 500.0, 1),
            "gramos_disponibles": disp_g
        })

    return {
        "inventario_disponible_g": max(0.0, total_comprado_general + total_ajustes_general - total_usado_general),
        "costo_promedio_gramo": (total_inversion_real / total_comprado_real) if total_comprado_real > 0 else 0.0,
        "productos_stock": resumen_tarjetas
    }

@app.post("/api/inventario/ajustar", status_code=201)
def ajustar_inventario_manual(ajuste: AjusteInventarioCreate, request: Request):
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
    if not db.productos.find_one({"nombre": nombre}):
        raise HTTPException(status_code=404, detail="El café seleccionado no existe.")

    gramos = round(ajuste.libras * 500.0, 2)

    if tipo == "salida":
        stock = resumen_inventario()["productos_stock"]
        disponible_g = next((p["gramos_disponibles"] for p in stock if p["nombre"] == nombre), 0.0)
        if gramos > disponible_g + 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"No puedes descontar {ajuste.libras} lbs: de '{nombre}' solo hay {round(disponible_g / 500.0, 1)} lbs disponibles."
            )

    signo = 1 if tipo == "entrada" else -1
    usuario = request.cookies.get("session_user", "admin")
    doc = {
        "fecha": datetime.utcnow().strftime("%Y-%m-%d"),
        "producto_nombre": nombre,
        "tipo": tipo,
        "libras": signo * ajuste.libras,
        "gramos": signo * gramos,
        "motivo": (ajuste.motivo or "").strip() or "Ajuste manual",
        "usuario": usuario,
        "creado_en": datetime.utcnow()
    }
    res = db.ajustes_inventario.insert_one(doc)
    accion = "sumaron" if tipo == "entrada" else "descontaron"
    return {"id": str(res.inserted_id), "mensaje": f"Se {accion} {ajuste.libras} lbs de {nombre} del inventario."}

@app.get("/api/inventario/ajustes")
def listar_ajustes_inventario():
    ajustes = list(db.ajustes_inventario.find().sort("creado_en", -1).limit(100))
    return [fix_id(a) for a in ajustes]

@app.put("/api/inventario/descontar-manual")
def descontar_stock_manual(data: dict, request: Request):
    """Compatibilidad con el endpoint anterior: ahora delega en el ajuste manual (tipo salida)."""
    try:
        libras = float(data.get("libras", 0.0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Cantidad de libras inválida.")
    ajuste = AjusteInventarioCreate(
        nombre=data.get("nombre") or "", libras=libras, tipo="salida",
        motivo=data.get("motivo") or "Descuento manual"
    )
    return ajustar_inventario_manual(ajuste, request)

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
        elif g == 2500:
            req_empaques["etiqueta_500g"] += cant

    for k, v_req in req_empaques.items():
        if v_req > resumen_emp[k]["disponibles"]:
            stock_insuficiente = True
            motivo_faltante[k] = v_req - resumen_emp[k]["disponibles"]

    estado_despacho = "Pendiente" if stock_insuficiente else "Completo"

    costo_cafe = 0.0
    for item in venta.items:
        prod = None
        if item.producto_id:
            try:
                prod = db.productos.find_one({"_id": ObjectId(item.producto_id)})
            except Exception:
                pass
        
        if not prod and item.nombre:
            prod = db.productos.find_one({"nombre": item.nombre})
            
        costo_libra = prod.get("costo_por_libra", 0.0) if prod else 0.0
        costo_gramo_item = (costo_libra / 500.0) if costo_libra > 0 else resumen_cafe["costo_promedio_gramo"]
        costo_cafe += item.gramos_totales * costo_gramo_item
    
    costo_empaques_total = 0.0
    for item in venta.items:
        cant = item.cantidad
        g = item.gramaje
        if g == 250:
            costo_empaques_total += cant * (resumen_emp["bolsa_250g"]["costo_unitario"] + resumen_emp["etiqueta_250g"]["costo_unitario"])
        elif g == 500:
            costo_empaques_total += cant * (resumen_emp["bolsa_500g"]["costo_unitario"] + resumen_emp["etiqueta_500g"]["costo_unitario"])
        elif g == 2500:
            costo_empaques_total += cant * resumen_emp["etiqueta_500g"]["costo_unitario"]

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
        "tipo_venta": venta.tipo_venta or "Normal",
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
    ventas_formateadas = []
    
    for v in ventas:
        v_clean = fix_id(v)
        
        if v_clean.get("tipo_pago") == "Efectivo":
            v_clean["tipo_pago"] = "Contado"

        v_clean["costo_envio_asociado"] = 0.0
        v_clean["ganancia"] = float(v_clean.get("ganancia", 0.0))
        
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
        elif g == 2500:
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

@app.put("/api/ventas/{venta_id}/anular")
@app.delete("/api/ventas/{venta_id}")
def anular_venta(venta_id: str):
    venta = db.ventas.find_one({"_id": ObjectId(venta_id)})
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    db.ventas.update_one(
        {"_id": ObjectId(venta_id)},
        {"$set": {
            "tipo_venta": "Anulado",
            "estado_despacho": "Anulado",
            "estado_credito": "Anulado",
            "total_venta": 0.0,
            "costo_estimado": 0.0,
            "ganancia": 0.0,
            "anulado_en": datetime.utcnow()
        }}
    )
    return {"mensaje": "Venta anulada correctamente"}

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
    
    if es_obsequio:
        tipo_pago_final = "N/A"
        estado_credito_final = "N/A"
    else:
        tipo_pago_final = "Contado" if nuevo_tipo_pago == "Efectivo" else nuevo_tipo_pago
        if tipo_pago_final == "Crédito":
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

# ==========================================
# ENDPOINTS PEDIDOS (COTIZACIONES)
# ==========================================

@app.post("/api/cotizaciones", status_code=201)
def registrar_cotizacion(cotizacion: VentaCreate, request: Request):
    vendedor = cotizacion.vendedor or request.cookies.get("session_user", "admin")
    es_obsequio = (cotizacion.tipo_venta == "Obsequio")
    total_cotizacion = 0.0 if es_obsequio else sum(i.subtotal for i in cotizacion.items)
    consecutivo = obtener_siguiente_consecutivo("cotizacion_num")

    tipo_pago_cot = "N/A" if es_obsequio else (cotizacion.tipo_pago if cotizacion.tipo_pago else "Contado")
    if tipo_pago_cot == "Efectivo":
        tipo_pago_cot = "Contado"

    doc = {
        "consecutivo_str": consecutivo,
        "fecha": cotizacion.fecha,
        "cliente": cotizacion.cliente,
        "vendedor": vendedor,
        "tipo_pago": tipo_pago_cot,
        "tipo_venta": cotizacion.tipo_venta or "Normal",
        "estado": "Pendiente",
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
        if "estado" not in c_item:
            c_item["estado"] = "Pendiente"
        cotizaciones_clean.append(c_item)
    return cotizaciones_clean

@app.put("/api/cotizaciones/{cotizacion_id}")
def editar_pedido(cotizacion_id: str, datos: VentaCreate, request: Request):
    """Edita un pedido que todavía NO se ha despachado, conservando su consecutivo."""
    try:
        oid = ObjectId(cotizacion_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de pedido inválido")

    pedido = db.cotizaciones.find_one({"_id": oid})
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    estado = pedido.get("estado", "Pendiente")
    if estado != "Pendiente":
        raise HTTPException(status_code=400, detail=f"Solo se pueden editar pedidos pendientes. Este pedido está '{estado}'.")

    usuario = request.cookies.get("session_user", "admin")
    user_doc = db.usuarios.find_one({"username": usuario})
    es_admin = bool(user_doc and user_doc.get("rol") == "admin")
    if not es_admin and pedido.get("vendedor") != usuario:
        raise HTTPException(status_code=403, detail="Solo puedes editar tus propios pedidos.")

    if not datos.items:
        raise HTTPException(status_code=400, detail="El pedido debe tener al menos un producto. Si ya no aplica, anúlalo.")

    # Se recalculan gramos y subtotales en el servidor (no se confía en los del navegador)
    items_limpios = []
    for it in datos.items:
        if it.cantidad <= 0:
            raise HTTPException(status_code=400, detail=f"La cantidad de '{it.nombre}' debe ser mayor a 0.")
        d = it.model_dump() if hasattr(it, "model_dump") else it.dict()
        precio = max(0.0, float(d.get("precio_unitario", 0.0)))
        desc = max(0.0, float(d.get("descuento", 0.0)))
        d["precio_unitario"] = precio
        d["descuento"] = desc
        d["gramos_totales"] = int(d["gramaje"]) * int(d["cantidad"])
        d["subtotal"] = max(0.0, (precio - desc) * d["cantidad"])
        items_limpios.append(d)

    es_obsequio = (datos.tipo_venta == "Obsequio")
    total_nuevo = 0.0 if es_obsequio else sum(i["subtotal"] for i in items_limpios)

    tipo_pago = "N/A" if es_obsequio else (datos.tipo_pago or "Contado")
    if tipo_pago == "Efectivo":
        tipo_pago = "Contado"

    cliente = (datos.cliente or "").strip() or "Cliente General"

    res = db.cotizaciones.update_one(
        {"_id": oid, "estado": {"$in": ["Pendiente", None]}},  # evita editar si lo despacharon mientras tanto
        {
            "$set": {
                "cliente": cliente,
                "tipo_pago": tipo_pago,
                "tipo_venta": datos.tipo_venta or "Normal",
                "total_venta": total_nuevo,
                "items": items_limpios,
                "editado_en": datetime.utcnow(),
                "editado_por": usuario
            },
            "$push": {
                "historial_ediciones": {
                    "fecha": datetime.utcnow(),
                    "usuario": usuario,
                    "total_anterior": float(pedido.get("total_venta", 0.0)),
                    "total_nuevo": total_nuevo,
                    "items_anteriores": pedido.get("items", [])
                }
            }
            # consecutivo_str, fecha, vendedor y creado_en NO se tocan
        }
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=409, detail="El pedido cambió de estado mientras lo editabas. Recarga la lista.")

    return {
        "id": cotizacion_id,
        "consecutivo": pedido.get("consecutivo_str", ""),
        "total_venta": total_nuevo,
        "mensaje": "Pedido actualizado correctamente"
    }

@app.post("/api/cotizaciones/{cotizacion_id}/despachar")
def despachar_pedido(cotizacion_id: str, request: Request):
    pedido = db.cotizaciones.find_one({"_id": ObjectId(cotizacion_id)})
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if pedido.get("estado", "Pendiente") != "Pendiente":
        raise HTTPException(status_code=400, detail=f"Este pedido ya está '{pedido.get('estado')}' y no se puede despachar.")

    resumen_cafe = resumen_inventario()
    resumen_emp = resumen_empaques()

    items = pedido.get("items", [])
    total_gramos = sum(i.get("gramos_totales", 0) for i in items)
    
    stock_insuficiente = False
    motivo_faltante = {}

    if total_gramos > resumen_cafe["inventario_disponible_g"]:
        stock_insuficiente = True
        motivo_faltante["cafe_g"] = total_gramos - resumen_cafe["inventario_disponible_g"]

    req_empaques = {"bolsa_250g": 0, "bolsa_500g": 0, "etiqueta_250g": 0, "etiqueta_500g": 0}
    for item in items:
        cant = item.get("cantidad", 0)
        g = item.get("gramaje", 0)
        if g == 250:
            req_empaques["bolsa_250g"] += cant
            req_empaques["etiqueta_250g"] += cant
        elif g == 500:
            req_empaques["bolsa_500g"] += cant
            req_empaques["etiqueta_500g"] += cant
        elif g == 2500:
            req_empaques["etiqueta_500g"] += cant

    for k, v_req in req_empaques.items():
        if v_req > resumen_emp[k]["disponibles"]:
            stock_insuficiente = True
            motivo_faltante[k] = v_req - resumen_emp[k]["disponibles"]

    estado_despacho = "Pendiente" if stock_insuficiente else "Completo"

    costo_cafe = 0.0
    for item in items:
        prod = None
        p_id = item.get("producto_id")
        if p_id:
            try:
                prod = db.productos.find_one({"_id": ObjectId(p_id)})
            except Exception:
                pass
        if not prod and item.get("nombre"):
            prod = db.productos.find_one({"nombre": item.get("nombre")})
            
        costo_libra = prod.get("costo_por_libra", 0.0) if prod else 0.0
        costo_gramo_item = (costo_libra / 500.0) if costo_libra > 0 else resumen_cafe["costo_promedio_gramo"]
        costo_cafe += item.get("gramos_totales", 0) * costo_gramo_item

    costo_empaques_total = 0.0
    for item in items:
        cant = item.get("cantidad", 0)
        g = item.get("gramaje", 0)
        if g == 250:
            costo_empaques_total += cant * (resumen_emp["bolsa_250g"]["costo_unitario"] + resumen_emp["etiqueta_250g"]["costo_unitario"])
        elif g == 500:
            costo_empaques_total += cant * (resumen_emp["bolsa_500g"]["costo_unitario"] + resumen_emp["etiqueta_500g"]["costo_unitario"])
        elif g == 2500:
            costo_empaques_total += cant * resumen_emp["etiqueta_500g"]["costo_unitario"]

    costo_est = round(costo_cafe + costo_empaques_total)
    consecutivo_venta = obtener_siguiente_consecutivo("factura_num")

    tipo_venta_pedido = pedido.get("tipo_venta", "Normal")
    tipo_pago = "N/A" if tipo_venta_pedido == "Obsequio" else pedido.get("tipo_pago", "Contado")
    if tipo_pago == "Efectivo":
        tipo_pago = "Contado"

    total_venta = float(pedido.get("total_venta", 0.0))

    doc_venta = {
        "consecutivo_str": consecutivo_venta,
        "pedido_origen_id": str(pedido["_id"]),
        "consecutivo_pedido": pedido.get("consecutivo_str", ""),
        "fecha": datetime.utcnow().strftime("%Y-%m-%d"),
        "cliente": pedido.get("cliente", "Cliente General"),
        "vendedor": pedido.get("vendedor", "admin"),
        "tipo_pago": tipo_pago,
        "tipo_venta": tipo_venta_pedido,
        "estado_despacho": estado_despacho,
        "faltantes": motivo_faltante if stock_insuficiente else {},
        "estado_credito": "Pendiente" if (tipo_pago == "Crédito" and tipo_venta_pedido != "Obsequio") else "N/A",
        "total_venta": total_venta,
        "costo_estimado": costo_est,
        "ganancia": total_venta - costo_est,
        "items": items,
        "creado_en": datetime.utcnow()
    }

    res_venta = db.ventas.insert_one(doc_venta)

    db.cotizaciones.update_one(
        {"_id": ObjectId(cotizacion_id)},
        {"$set": {"estado": "Despachado", "venta_asociada_id": str(res_venta.inserted_id)}}
    )

    return {
        "id_venta": str(res_venta.inserted_id),
        "consecutivo": consecutivo_venta,
        "estado_despacho": estado_despacho,
        "mensaje": "Pedido despachado y convertido a venta exitosamente"
    }

@app.get("/api/cotizaciones/{cotizacion_id}/pdf")
def descargar_cotizacion_pdf(cotizacion_id: str):
    cotizacion = db.cotizaciones.find_one({"_id": ObjectId(cotizacion_id)})
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    pdf_bytes = generar_factura_pdf(cotizacion, cotizacion["items"], es_cotizacion=True)
    num_cot = cotizacion.get("consecutivo_str", str(cotizacion_id)[:8])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=Pedido_{num_cot}.pdf"
        }
    )

@app.put("/api/cotizaciones/{cotizacion_id}/anular")
@app.delete("/api/cotizaciones/{cotizacion_id}")
def anular_cotizacion(cotizacion_id: str):
    cotizacion = db.cotizaciones.find_one({"_id": ObjectId(cotizacion_id)})
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    db.cotizaciones.update_one(
        {"_id": ObjectId(cotizacion_id)},
        {"$set": {
            "estado": "Anulado",
            "total_venta": 0.0,
            "anulado_en": datetime.utcnow()
        }}
    )
    return {"mensaje": "Pedido anulado correctamente"}
