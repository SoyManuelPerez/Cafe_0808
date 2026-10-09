import os
import io
import math
from datetime import datetime, date
from typing import List, Optional
from bson import ObjectId

from fastapi import FastAPI, Request, HTTPException, Depends, status, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

# ReportLab para generación de PDFs
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# -----------------------------------------------------------------------------
# CONFIGURACIÓN GENERAL Y DB
# -----------------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "cafe_0808_db")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

app = FastAPI(title="0808 Café de Especialidad - Sistema ERP")

# Servir archivos estáticos y plantillas Jinja2 si existen
app.mount("/static", StaticFiles(directory="static"), name="static") if os.path.exists("static") else None
templates = Jinja2Templates(directory="templates") if os.path.exists("templates") else None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Helper para conversión de ObjectId a String
def fix_id(doc):
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc

# -----------------------------------------------------------------------------
# AUTENTICACIÓN
# -----------------------------------------------------------------------------
async def get_current_user(request: Request):
    user_id = request.cookies.get("session_user")
    if not user_id:
        # Modo pruebas/desarrollo o verificar si no hay autenticación estricta
        user = await db.usuarios.find_one({"rol": "admin"})
        if user:
            return fix_id(user)
        return {"_id": "default_user", "username": "admin", "rol": "admin", "nombre": "Administrador"}
    
    user = await db.usuarios.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="Sesión no válida")
    return fix_id(user)

# -----------------------------------------------------------------------------
# MODELOS DE DATOS (PYDANTIC)
# -----------------------------------------------------------------------------
class ItemVenta(BaseModel):
    producto_id: str
    nombre: str
    cantidad: float
    precio_unitario: float
    tipo_presentacion: Optional[str] = "250g" # 250g, 500g, libra, etc.

class PedidoCreate(BaseModel):
    cliente_id: Optional[str] = None
    cliente_nombre: Optional[str] = "Cliente Ocasional"
    cliente_telefono: Optional[str] = ""
    cliente_direccion: Optional[str] = ""
    items: List[ItemVenta]
    forma_pago: str = "Efectivo"
    tipo_venta: str = "Normal" # Normal, Obsequio, Venta al Costo
    observaciones: Optional[str] = ""
    despachado: bool = False
    consecutivo_existente: Optional[int] = None # Para mantener consecutivo al editar

class ClienteModel(BaseModel):
    nombre: str
    celular: str
    email: Optional[str] = ""
    direccion: Optional[str] = ""

class InsumoAjuste(BaseModel):
    tipo: str # bolsa_250g, bolsa_500g, etiqueta_250g, etiqueta_500g
    cantidad: float
    costo_unitario: Optional[float] = 0.0

# -----------------------------------------------------------------------------
# RUTAS DE AUTENTICACIÓN Y NAVEGACIÓN PRINCIPAL
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    user = await db.usuarios.find_one({"username": username})
    if not user or not pwd_context.verify(password, user.get("password", "")):
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")
    
    response = JSONResponse(content={"mensaje": "Login exitoso", "rol": user.get("rol", "ventas")})
    response.set_cookie(key="session_user", value=str(user["_id"]), httponly=True)
    return response

@app.post("/api/logout")
async def logout():
    response = JSONResponse(content={"mensaje": "Sesión cerrada"})
    response.delete_cookie("session_user")
    return response

# -----------------------------------------------------------------------------
# CONTROL DE CONSECUTIVOS
# -----------------------------------------------------------------------------
async def obtener_siguiente_consecutivo(tipo: str) -> int:
    # tipo: 'factura' o 'pedido'
    doc = await db.consecutivos.find_one_and_update(
        {"tipo": tipo},
        {"$inc": {"valor": 1}},
        upsert=True,
        return_document=True
    )
    return doc.get("valor", 1)

# -----------------------------------------------------------------------------
# GESTIÓN DE CLIENTES
# -----------------------------------------------------------------------------
@app.get("/api/clientes")
async def listar_clientes():
    cursor = db.clientes.find().sort("nombre", 1)
    clientes = [fix_id(c) async for c in cursor]
    return clientes

@app.post("/api/clientes")
async def crear_cliente(cliente: ClienteModel):
    existente = await db.clientes.find_one({"celular": cliente.celular})
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe un cliente registrado con este número de celular")
    
    doc = cliente.dict()
    doc["fecha_registro"] = datetime.now()
    res = await db.clientes.insert_one(doc)
    return {"_id": str(res.inserted_id), "mensaje": "Cliente creado exitosamente"}

@app.put("/api/clientes/{cliente_id}")
async def actualizar_cliente(cliente_id: str, cliente: ClienteModel):
    res = await db.clientes.update_one(
        {"_id": ObjectId(cliente_id)},
        {"$set": cliente.dict()}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"mensaje": "Cliente actualizado exitosamente"}

# -----------------------------------------------------------------------------
# GESTIÓN DE INVENTARIO Y MATERIA PRIMA
# -----------------------------------------------------------------------------
@app.get("/api/inventario")
async def obtener_inventario():
    # Obtener inventario de café de especialidad y empaques
    cafe = await db.materia_prima.find_one({"tipo": "cafe_verde"}) or {"gramos": 0, "costo_por_gramo": 0}
    empaques = await db.insumos.find_one({"tipo": "empaques"}) or {
        "bolsa_250g": 0, "bolsa_500g": 0, 
        "etiqueta_250g": 0, "etiqueta_500g": 0,
        "costo_bolsa_250g": 0, "costo_bolsa_500g": 0,
        "costo_etiqueta_250g": 0, "costo_etiqueta_500g": 0
    }
    
    return {
        "cafe_verde_g": cafe.get("gramos", 0),
        "costo_gramo_cafe": cafe.get("costo_por_gramo", 0),
        "empaques": fix_id(empaques)
    }

@app.post("/api/inventario/insumos")
async def ajustar_insumos(insumo: InsumoAjuste):
    # Permite añadir o corregir cantidades de empaques o etiquetas
    campo_cantidad = insumo.tipo
    campo_costo = f"costo_{insumo.tipo}"
    
    await db.insumos.update_one(
        {"tipo": "empaques"},
        {
            "$inc": {campo_cantidad: insumo.cantidad},
            "$set": {campo_costo: insumo.costo_unitario}
        },
        upsert=True
    )
    return {"mensaje": f"Insumo {insumo.tipo} actualizado correctamente"}

# -----------------------------------------------------------------------------
# PEDIDOS Y COTIZACIONES (CON EDICIÓN DE PEDIDOS NO DESPACHADOS)
# -----------------------------------------------------------------------------
@app.get("/api/pedidos")
async def listar_pedidos():
    cursor = db.pedidos.find().sort("fecha", -1)
    pedidos = []
    async for p in cursor:
        p = fix_id(p)
        pedidos.append(p)
    return pedidos

@app.get("/api/pedidos/{pedido_id}")
async def obtener_pedido(pedido_id: str):
    pedido = await db.pedidos.find_one({"_id": ObjectId(pedido_id)})
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return fix_id(pedido)

@app.post("/api/pedidos")
async def crear_o_guardar_pedido(data: PedidoCreate):
    # Calcular total del pedido
    total = sum(item.cantidad * item.precio_unitario for item in data.items)
    
    # Manejar consecutivo (si viene de una edición se mantiene el mismo)
    if data.consecutivo_existente:
        consecutivo = data.consecutivo_existente
    else:
        consecutivo = await obtener_siguiente_consecutivo("pedido")

    doc_pedido = {
        "consecutivo": consecutivo,
        "cliente_id": data.cliente_id,
        "cliente_nombre": data.cliente_nombre,
        "cliente_telefono": data.cliente_telefono,
        "cliente_direccion": data.cliente_direccion,
        "items": [item.dict() for item in data.items],
        "total": total,
        "forma_pago": data.forma_pago,
        "tipo_venta": data.tipo_venta,
        "observaciones": data.observaciones,
        "despachado": data.despachado,
        "fecha": datetime.now()
    }

    res = await db.pedidos.insert_one(doc_pedido)
    return {
        "_id": str(res.inserted_id),
        "consecutivo": consecutivo,
        "mensaje": "Pedido registrado correctamente"
    }

@app.put("/api/pedidos/{pedido_id}")
async def actualizar_pedido(pedido_id: str, data: PedidoCreate):
    pedido_existente = await db.pedidos.find_one({"_id": ObjectId(pedido_id)})
    if not pedido_existente:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if pedido_existente.get("despachado", False):
        raise HTTPException(status_code=400, detail="No se puede editar un pedido que ya ha sido despachado")

    total = sum(item.cantidad * item.precio_unitario for item in data.items)
    
    # Mantenemos el consecutivo original intacto
    consecutivo = pedido_existente.get("consecutivo")

    actualizacion = {
        "cliente_id": data.cliente_id,
        "cliente_nombre": data.cliente_nombre,
        "cliente_telefono": data.cliente_telefono,
        "cliente_direccion": data.cliente_direccion,
        "items": [item.dict() for item in data.items],
        "total": total,
        "forma_pago": data.forma_pago,
        "tipo_venta": data.tipo_venta,
        "observaciones": data.observaciones,
        "fecha_actualizacion": datetime.now()
    }

    await db.pedidos.update_one({"_id": ObjectId(pedido_id)}, {"$set": actualizacion})

    return {
        "_id": pedido_id,
        "consecutivo": consecutivo,
        "mensaje": "Pedido actualizado conservando consecutivo exitosamente"
    }

@app.delete("/api/pedidos/{pedido_id}")
async def eliminar_pedido(pedido_id: str):
    pedido = await db.pedidos.find_one({"_id": ObjectId(pedido_id)})
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    
    if pedido.get("despachado", False):
        raise HTTPException(status_code=400, detail="No se puede eliminar un pedido despachado")

    await db.pedidos.delete_one({"_id": ObjectId(pedido_id)})
    return {"mensaje": "Pedido eliminado exitosamente"}

@app.post("/api/pedidos/{pedido_id}/despachar")
async def despachar_pedido(pedido_id: str):
    pedido = await db.pedidos.find_one({"_id": ObjectId(pedido_id)})
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    
    if pedido.get("despachado", False):
        raise HTTPException(status_code=400, detail="Este pedido ya fue despachado previamente")

    # Generar factura formal
    consecutivo_factura = await obtener_siguiente_consecutivo("factura")
    
    factura = {
        "consecutivo_factura": consecutivo_factura,
        "pedido_id": pedido_id,
        "cliente_nombre": pedido.get("cliente_nombre"),
        "cliente_id": pedido.get("cliente_id"),
        "items": pedido.get("items"),
        "total": pedido.get("total"),
        "forma_pago": pedido.get("forma_pago"),
        "fecha": datetime.now()
    }

    await db.facturas.insert_one(factura)
    await db.pedidos.update_one({"_id": ObjectId(pedido_id)}, {"$set": {"despachado": True, "factura_id": consecutivo_factura}})

    return {"mensaje": f"Pedido despachado con éxito. Generada Factura #{consecutivo_factura}"}

# -----------------------------------------------------------------------------
# IMPRESIÓN Y PDF DE PEDIDOS / FACTURAS
# -----------------------------------------------------------------------------
@app.get("/api/pedidos/{pedido_id}/pdf")
async def generar_pdf_pedido(pedido_id: str):
    pedido = await db.pedidos.find_one({"_id": ObjectId(pedido_id)})
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#8B5A2B'),
        alignment=1,
        spaceAfter=10
    )
    normal_style = styles['Normal']

    story.append(Paragraph("<b>0808 CAFÉ DE ESPECIALIDAD</b>", title_style))
    story.append(Paragraph(f"<b>PEDIDO / COTIZACIÓN N°: #{pedido.get('consecutivo', '000')}</b>", styles['Heading3']))
    story.append(Paragraph(f"<b>Fecha:</b> {pedido.get('fecha', datetime.now()).strftime('%Y-%m-%d %H:%M')}", normal_style))
    story.append(Paragraph(f"<b>Cliente:</b> {pedido.get('cliente_nombre', 'Cliente Ocasional')}", normal_style))
    story.append(Paragraph(f"<b>Forma de Pago:</b> {pedido.get('forma_pago', 'Efectivo')}", normal_style))
    story.append(Spacer(1, 15))

    # Tabla de productos
    tabla_datos = [["Producto / Presentación", "Cantidad", "P. Unitario", "Subtotal"]]
    for item in pedido.get("items", []):
        subtotal = item['cantidad'] * item['precio_unitario']
        tabla_datos.append([
            f"{item['nombre']} ({item.get('tipo_presentacion', '250g')})",
            str(item['cantidad']),
            f"${item['precio_unitario']:,.0f}",
            f"${subtotal:,.0f}"
        ])

    tabla_datos.append(["", "", "<b>TOTAL:</b>", f"<b>${pedido.get('total', 0):,.0f}</b>"])

    t = Table(tabla_datos, colWidths=[250, 80, 100, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B5A2B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('LINEABOVE', (2, -1), (-1, -1), 1, colors.black),
    ]))

    story.append(t)
    
    if pedido.get("observaciones"):
        story.append(Spacer(1, 15))
        story.append(Paragraph(f"<b>Observaciones:</b> {pedido.get('observaciones')}", normal_style))

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=pedido_{pedido.get('consecutivo')}.pdf"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
