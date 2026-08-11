import os
import uuid
import datetime
import math
from io import BytesIO
from typing import List, Optional

import pymongo
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

app = FastAPI(title="0808 Café de Especialidad")

# Montar estáticos y plantillas
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# -------------------------------------------------------------------
# CONEXIÓN MONGODB (Lee la variable MONGO_URI configurada en Render)
# -------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

if "localhost" in MONGO_URI:
    print("⚠️ ADVERTENCIA: Conectando a localhost. Si estás en Render, verifica tus variables de entorno.")
else:
    print("✅ Conectando a base de datos remota MongoDB mediante MONGO_URI.")

client = pymongo.MongoClient(MONGO_URI)
db = client["gestion_cafe"]

# -------------------------------------------------------------------
# MODELOS DE DATOS (PYDANTIC)
# -------------------------------------------------------------------
class ItemCarrito(BaseModel):
    producto_id: str
    nombre: str
    gramaje: float
    cantidad: int
    valor_add: Optional[float] = 0.0
    descuento: Optional[float] = 0.0
    presentacion: Optional[str] = "Grano"
    gramos_totales: float
    precio_unitario: float
    subtotal: float

class VentaCreate(BaseModel):
    fecha: str
    cliente: str
    vendedor: str
    tipo_pago: str
    tipo_venta: Optional[str] = "Normal"
    items: List[ItemCarrito]

class CotizacionCreate(BaseModel):
    fecha: str
    cliente: str
    vendedor: str
    tipo_pago: str
    items: List[ItemCarrito]

class ProductoCreate(BaseModel):
    nombre: str
    gramaje: float
    precio_venta: float

class ProductoUpdate(BaseModel):
    nombre: str
    precio_venta: float

class ClienteCreate(BaseModel):
    nombre: str
    celular: Optional[str] = ""

class CompraCreate(BaseModel):
    fecha: str
    libras: float
    costo_total: float
    producto_id: Optional[str] = None

class CompraEmpaqueCreate(BaseModel):
    tipo_empaque: str
    fecha: str
    cantidad: int
    costo_total: float

class AjusteEmpaque(BaseModel):
    tipo_empaque: str
    disponibles: int
    costo_unitario: float

class UsuarioCreate(BaseModel):
    username: str
    password: str
    rol: str

class UsuarioUpdate(BaseModel):
    username: str
    password: Optional[str] = None
    rol: str

class LoginRequest(BaseModel):
    username: str
    password: str

# MODELOS PARA ENVÍOS CONSOLIDADOS
class ItemEnvio(BaseModel):
    producto_id: str
    nombre: str
    gramaje: float
    cantidad: int

class EnvioCreate(BaseModel):
    fecha: str
    nota: str
    valor_envio: float
    items: List[ItemEnvio]

class AsociarFacturasRequest(BaseModel):
    facturas_ids: List[str]

# -------------------------------------------------------------------
# FUNCIONES AUXILIARES DE CONSECUTIVOS Y BBDD
# -------------------------------------------------------------------
def obtener_siguiente_consecutivo(tipo: str) -> int:
    doc = db.consecutivos.find_one_and_update(
        {"_id": tipo},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=pymongo.ReturnDocument.AFTER
    )
    return doc["seq"]

# Crear usuario admin inicial si no existe
def init_db():
    try:
        if db.usuarios.count_documents({"username": "admin"}) == 0:
            db.usuarios.insert_one({
                "id": str(uuid.uuid4()),
                "username": "admin",
                "password": "123",
                "rol": "admin"
            })
    except Exception as e:
        print(f"Advertencia inicializando base de datos: {e}")

init_db()

# -------------------------------------------------------------------
# RUTAS VISTAS Y AUTENTICACIÓN
# -------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/login")
async def login(req: LoginRequest):
    user = db.usuarios.find_one({"username": req.username, "password": req.password})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return {"username": user["username"], "rol": user["rol"]}

@app.post("/api/logout")
async def logout():
    return {"status": "ok"}

# -------------------------------------------------------------------
# RUTAS USUARIOS
# -------------------------------------------------------------------
@app.get("/api/usuarios")
async def listar_usuarios():
    return list(db.usuarios.find({}, {"_id": 0}))

@app.post("/api/usuarios")
async def crear_usuario(u: UsuarioCreate):
    if db.usuarios.find_one({"username": u.username}):
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
    usr = {"id": str(uuid.uuid4()), "username": u.username, "password": u.password, "rol": u.rol}
    db.usuarios.insert_one(usr)
    return {"status": "ok"}

@app.put("/api/usuarios/{usr_id}")
async def actualizar_usuario(usr_id: str, u: UsuarioUpdate):
    usr = db.usuarios.find_one({"id": usr_id})
    if not usr:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    update_data = {"username": u.username, "rol": u.rol}
    if u.password and u.password.strip():
        update_data["password"] = u.password.strip()

    db.usuarios.update_one({"id": usr_id}, {"$set": update_data})
    return {"status": "ok"}

@app.delete("/api/usuarios/{usr_id}")
async def eliminar_usuario(usr_id: str):
    usr = db.usuarios.find_one({"id": usr_id})
    if usr and usr["username"] == "admin":
        raise HTTPException(status_code=400, detail="No se puede eliminar el usuario admin principal")
    db.usuarios.delete_one({"id": usr_id})
    return {"status": "ok"}

# -------------------------------------------------------------------
# RUTAS CLIENTES
# -------------------------------------------------------------------
@app.get("/api/clientes")
async def listar_clientes():
    return list(db.clientes.find({}, {"_id": 0}))

@app.post("/api/clientes")
async def crear_cliente(c: ClienteCreate):
    cli = {"id": str(uuid.uuid4()), "nombre": c.nombre, "celular": c.celular or ""}
    db.clientes.insert_one(cli)
    return {"status": "ok", "nombre": c.nombre}

@app.put("/api/clientes/{cli_id}")
async def actualizar_cliente(cli_id: str, c: ClienteCreate):
    db.clientes.update_one({"id": cli_id}, {"$set": {"nombre": c.nombre, "celular": c.celular or ""}})
    return {"status": "ok"}

@app.delete("/api/clientes/{cli_id}")
async def eliminar_cliente(cli_id: str):
    db.clientes.delete_one({"id": cli_id})
    return {"status": "ok"}

# -------------------------------------------------------------------
# RUTAS PRODUCTOS & INVENTARIO
# -------------------------------------------------------------------
@app.get("/api/productos")
async def listar_productos():
    return list(db.productos.find({}, {"_id": 0}))

@app.get("/api/productos/unicos")
async def listar_productos_unicos():
    prods = list(db.productos.find({}, {"_id": 0}))
    unicos = {}
    for p in prods:
        if p["nombre"] not in unicos:
            unicos[p["nombre"]] = p
    return list(unicos.values())

@app.post("/api/productos")
async def crear_producto(p: ProductoCreate):
    prod = {
        "id": str(uuid.uuid4()),
        "nombre": p.nombre,
        "gramaje": p.gramaje,
        "precio_venta": p.precio_venta,
        "costo_por_libra": 0.0
    }
    db.productos.insert_one(prod)
    return {"status": "ok"}

@app.put("/api/productos/{prod_id}")
async def actualizar_producto(prod_id: str, p: ProductoUpdate):
    db.productos.update_one({"id": prod_id}, {"$set": {"nombre": p.nombre, "precio_venta": p.precio_venta}})
    return {"status": "ok"}

@app.delete("/api/productos/{prod_id}")
async def eliminar_producto(prod_id: str):
    db.productos.delete_one({"id": prod_id})
    return {"status": "ok"}

@app.put("/api/productos/actualizar-costo-libra")
async def actualizar_costo_libra(data: dict):
    nombre = data.get("nombre")
    costo = float(data.get("costo_por_libra", 0))
    db.productos.update_many({"nombre": nombre}, {"$set": {"costo_por_libra": costo}})
    return {"status": "ok"}

# -------------------------------------------------------------------
# COMPRAS DE CAFÉ Y EMPAQUES
# -------------------------------------------------------------------
@app.get("/api/compras")
async def listar_compras():
    compras = list(db.compras.find({}, {"_id": 0}))
    for c in compras:
        c["costo_por_libra"] = (c["costo_total"] / c["libras"]) if c["libras"] > 0 else 0
    return compras

@app.post("/api/compras")
async def registrar_compra(c: CompraCreate):
    costo_libra = (c.costo_total / c.libras) if c.libras > 0 else 0
    prod_nombre = None
    if c.producto_id:
        p = db.productos.find_one({"id": c.producto_id})
        if p:
            prod_nombre = p["nombre"]
            db.productos.update_many({"nombre": prod_nombre}, {"$set": {"costo_por_libra": costo_libra}})

    compra_doc = {
        "id": str(uuid.uuid4()),
        "fecha": c.fecha,
        "libras": c.libras,
        "costo_total": c.costo_total,
        "producto_id": c.producto_id,
        "producto_nombre": prod_nombre,
        "costo_por_libra": costo_libra
    }
    db.compras.insert_one(compra_doc)
    return {"status": "ok"}

@app.get("/api/compras-empaques")
async def listar_compras_empaques():
    return list(db.compras_empaques.find({}, {"_id": 0}))

@app.post("/api/compras-empaques")
async def registrar_compra_empaque(e: CompraEmpaqueCreate):
    costo_unit = (e.costo_total / e.cantidad) if e.cantidad > 0 else 0
    doc = {
        "id": str(uuid.uuid4()),
        "tipo_empaque": e.tipo_empaque,
        "fecha": e.fecha,
        "cantidad": e.cantidad,
        "costo_total": e.costo_total,
        "costo_unitario": costo_unit
    }
    db.compras_empaques.insert_one(doc)
    return {"status": "ok"}

@app.get("/api/empaques/resumen")
async def resumen_empaques():
    tipos = ["bolsa_250g", "bolsa_500g", "etiqueta_250g", "etiqueta_500g"]
    resumen = {}

    for t in tipos:
        compras = list(db.compras_empaques.find({"tipo_empaque": t}))
        comprados = sum([c["cantidad"] for c in compras])
        ultimo_costo = compras[-1]["costo_unitario"] if compras else 0.0

        ventas = list(db.ventas.find({"estado_despacho": {"$ne": "Pendiente"}}))
        usados = 0
        for v in ventas:
            for item in v.get("items", []):
                g = item.get("gramaje", 0)
                cant = item.get("cantidad", 0)
                if "bolsa" in t:
                    if t == "bolsa_250g" and g == 250: usados += cant
                    elif t == "bolsa_500g" and g == 500: usados += cant
                elif "etiqueta" in t:
                    if t == "etiqueta_250g" and g == 250: usados += cant
                    elif t == "etiqueta_500g" and g == 500: usados += cant

        ajuste = db.ajustes_empaques.find_one({"tipo_empaque": t})
        disponibles = ajuste["disponibles"] if ajuste else (comprados - usados)
        costo_u = ajuste["costo_unitario"] if ajuste else ultimo_costo

        resumen[t] = {
            "comprados": comprados,
            "usados": usados,
            "disponibles": max(0, disponibles),
            "costo_unitario": costo_u
        }
    return resumen

@app.put("/api/empaques/ajuste-manual")
async def ajuste_manual_empaque(a: AjusteEmpaque):
    db.ajustes_empaques.update_one(
        {"tipo_empaque": a.tipo_empaque},
        {"$set": {"disponibles": a.disponibles, "costo_unitario": a.costo_unitario}},
        upsert=True
    )
    return {"status": "ok"}

@app.get("/api/inventario/resumen")
async def resumen_inventario():
    productos = list(db.productos.find({}, {"_id": 0}))
    compras = list(db.compras.find({}, {"_id": 0}))
    ventas = list(db.ventas.find({"estado_despacho": {"$ne": "Pendiente"}}, {"_id": 0}))

    resumen_prods = []
    unicos_nombres = list(set([p["nombre"] for p in productos]))

    for nom in unicos_nombres:
        lbs_compradas = sum([c["libras"] for c in compras if c.get("producto_nombre") == nom])
        
        lbs_vendidas = 0.0
        for v in ventas:
            for item in v.get("items", []):
                if item.get("nombre") == nom:
                    gramos_totales = item.get("gramos_totales", item.get("gramaje", 0) * item.get("cantidad", 0))
                    lbs_vendidas += (gramos_totales / 500.0)

        lbs_disponibles = max(0.0, round(lbs_compradas - lbs_vendidas, 2))
        resumen_prods.append({
            "nombre": nom,
            "libras_compradas": lbs_compradas,
            "libras_vendidas": round(lbs_vendidas, 2),
            "libras_disponibles": lbs_disponibles
        })

    return {"productos_stock": resumen_prods}

# -------------------------------------------------------------------
# ENVÍOS CONSOLIDADOS A VENDEDORES
# -------------------------------------------------------------------
@app.get("/api/envios")
async def listar_envios():
    return list(db.envios.find({}, {"_id": 0}))

@app.post("/api/envios")
async def crear_envio(data: EnvioCreate):
    nuevo_envio = {
        "id": str(uuid.uuid4()),
        "fecha": data.fecha,
        "nota": data.nota,
        "valor_envio": data.valor_envio,
        "items": [item.dict() for item in data.items],
        "facturas_ids": []
    }
    db.envios.insert_one(nuevo_envio)
    return {"status": "ok", "id": nuevo_envio["id"]}

@app.put("/api/envios/{envio_id}/asociar-facturas")
async def asociar_facturas_envio(envio_id: str, req: AsociarFacturasRequest):
    db.envios.update_one({"id": envio_id}, {"$set": {"facturas_ids": req.facturas_ids}})
    return {"status": "ok"}

@app.delete("/api/envios/{envio_id}")
async def eliminar_envio(envio_id: str):
    db.envios.delete_one({"id": envio_id})
    return {"status": "ok"}

# -------------------------------------------------------------------
# RUTAS VENTAS Y COTIZACIONES
# -------------------------------------------------------------------
@app.get("/api/ventas")
async def listar_ventas():
    ventas = list(db.ventas.find({}, {"_id": 0}))
    envios = list(db.envios.find({}, {"_id": 0}))

    fletes_por_factura = {}
    for env in envios:
        facturas = env.get("facturas_ids", [])
        num_facturas = len(facturas)
        if num_facturas > 0:
            flete_unitario = env.get("valor_envio", 0.0) / num_facturas
            for f_id in facturas:
                fletes_por_factura[f_id] = fletes_por_factura.get(f_id, 0.0) + flete_unitario

    for v in ventas:
        flete_aplicado = fletes_por_factura.get(v["id"], 0.0)
        v["costo_envio_asociado"] = flete_aplicado
        v["ganancia"] = v.get("ganancia_bruta", v.get("ganancia", 0.0)) - flete_aplicado

    return ventas

@app.post("/api/ventas")
async def registrar_venta(v: VentaCreate):
    consecutivo = obtener_siguiente_consecutivo("ventas")
    consecutivo_str = f"FACT-{consecutivo:05d}"

    resumen_emp = await resumen_empaques()
    resumen_inv = await resumen_inventario()

    faltantes = {}
    es_obsequio = (v.tipo_venta == "Obsequio")

    for item in v.items:
        g = item.gramaje
        cant = item.cantidad
        nom = item.nombre

        stock_item = next((s for s in resumen_inv["productos_stock"] if s["nombre"] == nom), None)
        lbs_necesarias = (g * cant) / 500.0
        if not stock_item or stock_item["libras_disponibles"] < lbs_necesarias:
            disp = stock_item["libras_disponibles"] if stock_item else 0
            faltantes[f"Café {nom}"] = f"Req: {lbs_necesarias} Lbs, Disp: {disp} Lbs"

        if g in [250, 500]:
            k_bolsa = f"bolsa_{int(g)}g"
            k_etiq = f"etiqueta_{int(g)}g"

            if resumen_emp[k_bolsa]["disponibles"] < cant:
                faltantes[f"Bolsas {g}g"] = f"Req: {cant}, Disp: {resumen_emp[k_bolsa]['disponibles']}"
            if resumen_emp[k_etiq]["disponibles"] < cant:
                faltantes[f"Etiquetas {g}g"] = f"Req: {cant}, Disp: {resumen_emp[k_etiq]['disponibles']}"

    estado_despacho = "Pendiente" if len(faltantes) > 0 else "Completo"

    costo_total_venta = 0.0
    total_venta = 0.0

    items_procesados = []
    for item in v.items:
        p = db.productos.find_one({"id": item.producto_id})
        costo_lb = p.get("costo_por_libra", 0.0) if p else 0.0
        costo_cafe = (item.gramos_totales / 500.0) * costo_lb

        g = item.gramaje
        costo_bolsa = resumen_emp.get(f"bolsa_{int(g)}g", {}).get("costo_unitario", 0.0)
        costo_etiq = resumen_emp.get(f"etiqueta_{int(g)}g", {}).get("costo_unitario", 0.0)
        costo_insumos = (costo_bolsa + costo_etiq) * item.cantidad

        costo_item = costo_cafe + costo_insumos
        costo_total_venta += costo_item

        subt = 0.0 if es_obsequio else item.subtotal
        total_venta += subt

        item_dict = item.dict()
        item_dict["costo_produccion"] = costo_item
        items_procesados.append(item_dict)

    ganancia_bruta = 0.0 if es_obsequio else (total_venta - costo_total_venta)

    venta_doc = {
        "id": str(uuid.uuid4()),
        "consecutivo": consecutivo,
        "consecutivo_str": consecutivo_str,
        "fecha": v.fecha,
        "cliente": v.cliente,
        "vendedor": v.vendedor,
        "tipo_pago": v.tipo_pago,
        "tipo_venta": v.tipo_venta or "Normal",
        "estado_despacho": estado_despacho,
        "estado_credito": "Pendiente" if v.tipo_pago == "Crédito" else "N/A",
        "faltantes": faltantes,
        "items": items_procesados,
        "costo_total_produccion": costo_total_venta,
        "total_venta": total_venta,
        "ganancia_bruta": ganancia_bruta,
        "ganancia": ganancia_bruta
    }

    db.ventas.insert_one(venta_doc)
    return {"status": "ok", "id": venta_doc["id"], "consecutivo": consecutivo_str, "estado_despacho": estado_despacho}

@app.put("/api/ventas/{venta_id}/completar-despacho")
async def completar_despacho(venta_id: str):
    v = db.ventas.find_one({"id": venta_id})
    if not v:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    db.ventas.update_one({"id": venta_id}, {"$set": {"estado_despacho": "Completo", "faltantes": {}}})
    return {"status": "ok"}

@app.put("/api/ventas/{venta_id}/pagar-credito")
async def pagar_credito_venta(venta_id: str):
    db.ventas.update_one({"id": venta_id}, {"$set": {"estado_credito": "Pagado"}})
    return {"status": "ok"}

@app.delete("/api/ventas/{venta_id}")
async def eliminar_venta(venta_id: str):
    db.ventas.delete_one({"id": venta_id})
    return {"status": "ok"}

@app.get("/api/cotizaciones")
async def listar_cotizaciones():
    return list(db.cotizaciones.find({}, {"_id": 0}))

@app.post("/api/cotizaciones")
async def registrar_cotizacion(c: CotizacionCreate):
    consecutivo = obtener_siguiente_consecutivo("cotizaciones")
    consecutivo_str = f"COT-{consecutivo:05d}"
    total = sum([item.subtotal for item in c.items])

    cot_doc = {
        "id": str(uuid.uuid4()),
        "consecutivo": consecutivo,
        "consecutivo_str": consecutivo_str,
        "fecha": c.fecha,
        "cliente": c.cliente,
        "vendedor": c.vendedor,
        "tipo_pago": c.tipo_pago,
        "items": [item.dict() for item in c.items],
        "total_venta": total
    }
    db.cotizaciones.insert_one(cot_doc)
    return {"status": "ok", "id": cot_doc["id"], "consecutivo": consecutivo_str}

@app.delete("/api/cotizaciones/{cot_id}")
async def eliminar_cotizacion(cot_id: str):
    db.cotizaciones.delete_one({"id": cot_id})
    return {"status": "ok"}

# -------------------------------------------------------------------
# GENERACIÓN DE PDFS (FACTURAS Y COTIZACIONES)
# -------------------------------------------------------------------
def generar_pdf_documento(titulo_doc: str, num_doc: str, fecha: str, cliente: str, vendedor: str, tipo_pago: str, items: list, total: float) -> bytes:
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter

    # Encabezado
    p.setFillColor(colors.HexColor("#0D0D0D"))
    p.rect(0, h - 100, w, 100, fill=1)

    p.setFillColor(colors.HexColor("#D4AF37"))
    p.setFont("Helvetica-Bold", 20)
    p.drawString(40, h - 45, "0808 CAFÉ DE ESPECIALIDAD")

    p.setFont("Helvetica", 10)
    p.setFillColor(colors.white)
    p.drawString(40, h - 65, "Barbosa, Antioquia, Colombia | WhatsApp: +57 300 000 0000")

    p.setFillColor(colors.HexColor("#FFD700"))
    p.setFont("Helvetica-Bold", 14)
    p.drawRightString(w - 40, h - 45, titulo_doc)
    p.drawString(w - 160, h - 65, f"N°: {num_doc}")

    # Información Cliente y Transacción
    p.setFillColor(colors.HexColor("#1A1A1A"))
    p.rect(40, h - 170, w - 80, 55, fill=1, stroke=0)

    p.setFillColor(colors.HexColor("#D4AF37"))
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, h - 130, f"FECHA: {fecha}")
    p.drawString(50, h - 150, f"CLIENTE: {cliente}")

    p.drawString(w/2 + 20, h - 130, f"VENDEDOR: {vendedor}")
    p.drawString(w/2 + 20, h - 150, f"FORMA DE PAGO: {tipo_pago}")

    # Tabla de Productos
    y = h - 200
    p.setFillColor(colors.HexColor("#1A1813"))
    p.rect(40, y, w - 80, 20, fill=1, stroke=0)

    p.setFillColor(colors.HexColor("#D4AF37"))
    p.setFont("Helvetica-Bold", 9)
    p.drawString(50, y + 6, "PRODUCTO")
    p.drawString(220, y + 6, "PRES.")
    p.drawString(280, y + 6, "GRAMAJE")
    p.drawString(350, y + 6, "CANT.")
    p.drawString(410, y + 6, "PRECIO UNIT.")
    p.drawRightString(w - 50, y + 6, "SUBTOTAL")

    y -= 20
    p.setFont("Helvetica", 9)
    p.setFillColor(colors.black)

    for item in items:
        p.drawString(50, y + 5, str(item.get("nombre", "")))
        p.drawString(220, y + 5, str(item.get("presentacion", "Grano")))
        p.drawString(280, y + 5, f"{item.get('gramaje', 0)}g")
        p.drawString(350, y + 5, str(item.get("cantidad", 0)))
        
        pu = item.get("precio_unitario", 0)
        sub = item.get("subtotal", 0)
        p.drawString(410, y + 5, f"${pu:,.0f}".replace(",", "."))
        p.drawRightString(w - 50, y + 5, f"${sub:,.0f}".replace(",", "."))

        p.setStrokeColor(colors.HexColor("#E0E0E0"))
        p.line(40, y, w - 40, y)
        y -= 20

    # Total General
    y -= 10
    p.setFillColor(colors.HexColor("#1A1A1A"))
    p.rect(w - 240, y - 10, 200, 25, fill=1, stroke=0)

    p.setFillColor(colors.HexColor("#FFD700"))
    p.setFont("Helvetica-Bold", 12)
    p.drawString(w - 230, y, "TOTAL:")
    p.drawRightString(w - 50, y, f"${total:,.0f}".replace(",", "."))

    p.save()
    pdf_out = buffer.getvalue()
    buffer.close()
    return pdf_out

@app.get("/api/ventas/{venta_id}/pdf")
async def descargar_pdf_venta(venta_id: str):
    v = db.ventas.find_one({"id": venta_id})
    if not v:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    pdf_bytes = generar_pdf_documento(
        titulo_doc="FACTURA DE VENTA",
        num_doc=v.get("consecutivo_str", v["id"][:8]),
        fecha=v["fecha"],
        cliente=v["cliente"],
        vendedor=v.get("vendedor", "admin"),
        tipo_pago=v.get("tipo_pago", "Efectivo"),
        items=v.get("items", []),
        total=v.get("total_venta", 0.0)
    )

    return Response(content=pdf_bytes, media_type="application/pdf")

@app.get("/api/cotizaciones/{cot_id}/pdf")
async def descargar_pdf_cotizacion(cot_id: str):
    c = db.cotizaciones.find_one({"id": cot_id})
    if not c:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    pdf_bytes = generar_pdf_documento(
        titulo_doc="COTIZACIÓN",
        num_doc=c.get("consecutivo_str", c["id"][:8]),
        fecha=c["fecha"],
        cliente=c["cliente"],
        vendedor=c.get("vendedor", "admin"),
        tipo_pago=c.get("tipo_pago", "Efectivo"),
        items=c.get("items", []),
        total=c.get("total_venta", 0.0)
    )

    return Response(content=pdf_bytes, media_type="application/pdf")
