# app/main.py - Código Backend Completo
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Security, Header
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from google.oauth2 import service_account
from googleapiclient.discovery import build

import jwt

# ---------------------------------------------------------
# RESOLUCIÓN DE RUTAS DEL PROYECTO
# ---------------------------------------------------------
# Ruta hacia el directorio app/
BASE_DIR = Path(__file__).resolve().parent

# Ruta raíz del proyecto (un nivel arriba de app/)
PROJECT_ROOT = BASE_DIR.parent

TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

# ---------------------------------------------------------
# CONFIGURACIÓN Y CONSTANTES
# ---------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "tu_clave_secreta_aqui_para_jwt")
ALGORITHM = "HS256"

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")

COL_VENTAS = {
    "ID": 0, "FACTURA": 1, "FECHA": 2, "VENDEDOR": 3, "CLIENTE": 4,
    "TIPO_PAGO": 5, "TOTAL": 6, "GANANCIA": 7, "DETALLES": 8
}

COL_CREDITOS = {
    "ID_VENTA": 0, "FACTURA": 1, "FECHA": 2, "CLIENTE": 3,
    "VENDEDOR": 4, "TOTAL": 5, "ESTADO": 6
}

# ---------------------------------------------------------
# INICIALIZACIÓN Y DEPENDENCIAS
# ---------------------------------------------------------
app = FastAPI(title="Sistema de Gestión de Ventas")
security = HTTPBearer()

def obtener_servicio_sheets():
    if not GOOGLE_CREDENTIALS_JSON or not SPREADSHEET_ID:
        raise HTTPException(status_code=500, detail="Configuración de Google Sheets no encontrada en variables de entorno.")
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', '4', credentials=creds)
        return service.spreadsheets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al conectar con Google Sheets: {str(e)}")

def verificar_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

# ---------------------------------------------------------
# MODELOS DE DATOS (PYDANTIC)
# ---------------------------------------------------------
class LoginModel(BaseModel):
    usuario: str
    password: str

class DetalleVenta(BaseModel):
    producto: str
    cantidad: int
    precio_venta: float
    costo: float

class CrearVentaModel(BaseModel):
    cliente: str
    tipo_pago: str  # "Contado" o "Crédito"
    detalles: List[DetalleVenta]

class EditarDetallesVentaModel(BaseModel):
    cliente: str
    tipo_pago: str

class PagarCreditoModel(BaseModel):
    venta_id: str

# ---------------------------------------------------------
# RUTAS DE ARCHIVOS ESTÁTICOS Y TEMPLATES
# ---------------------------------------------------------
@app.get("/")
def read_root():
    index_path = TEMPLATES_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail=f"No se encontró index.html en: {index_path}")
    return FileResponse(index_path)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------
# ENDPOINTS DE AUTENTICACIÓN
# ---------------------------------------------------------
@app.post("/api/login")
def login(datos: LoginModel):
    sheets = obtener_servicio_sheets()
    res = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range="Usuarios!A2:C").execute()
    filas = res.get('values', [])
    
    usuario_encontrado = None
    for f in filas:
        if len(f) >= 3 and f[0].strip().lower() == datos.usuario.strip().lower() and f[1] == datos.password:
            usuario_encontrado = {"usuario": f[0], "rol": f[2]}
            break
            
    if not usuario_encontrado:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
        
    token = jwt.encode(usuario_encontrado, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "usuario": usuario_encontrado["usuario"], "rol": usuario_encontrado["rol"]}

# ---------------------------------------------------------
# ENDPOINTS DE CLIENTES
# ---------------------------------------------------------
@app.get("/api/clientes")
def obtener_clientes(usuario: dict = Depends(verificar_token)):
    sheets = obtener_servicio_sheets()
    res = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range="Clientes!A2:C").execute()
    filas = res.get('values', [])
    
    clientes = []
    for f in filas:
        if f:
            clientes.append({
                "nombre": f[0] if len(f) > 0 else "",
                "celular": f[1] if len(f) > 1 else "",
                "direccion": f[2] if len(f) > 2 else ""
            })
    return clientes

# ---------------------------------------------------------
# ENDPOINT DE EDICIÓN DE VENTA
# ---------------------------------------------------------
@app.put("/api/ventas/{venta_id}/editar-detalles")
def editar_detalles_venta(venta_id: str, datos: EditarDetallesVentaModel, usuario: dict = Depends(verificar_token)):
    sheets = obtener_servicio_sheets()
    
    # 1. Buscar la venta en la hoja Ventas
    res_v = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range="Ventas!A2:I").execute()
    filas_v = res_v.get('values', [])
    
    fila_venta_idx = -1
    venta_actual = None
    for idx, f in enumerate(filas_v):
        if f and f[COL_VENTAS["ID"]] == venta_id:
            fila_venta_idx = idx + 2  # Offset por encabezado (Fila 1)
            venta_actual = f
            break
            
    if fila_venta_idx == -1 or not venta_actual:
        raise HTTPException(status_code=404, detail="La venta no fue encontrada.")
        
    # Validar permisos (Solo admin o el vendedor original pueden editar)
    if usuario["rol"] != "admin" and venta_actual[COL_VENTAS["VENDEDOR"]] != usuario["usuario"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para modificar esta venta.")

    nuevo_cliente = datos.cliente.strip()
    nuevo_tipo_pago = datos.tipo_pago.strip()  # "Contado" o "Crédito"

    # 2. Actualizar en hoja Ventas (Columnas E y F: Cliente y Tipo de Pago)
    sheets.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Ventas!E{fila_venta_idx}:F{fila_venta_idx}",
        valueInputOption="USER_ENTERED",
        body={"values": [[nuevo_cliente, nuevo_tipo_pago]]}
    ).execute()

    # 3. Sincronizar hoja Créditos
    res_c = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range="Creditos!A2:G").execute()
    filas_c = res_c.get('values', [])
    
    fila_credito_idx = -1
    for idx, f in enumerate(filas_c):
        if f and f[COL_CREDITOS["ID_VENTA"]] == venta_id:
            fila_credito_idx = idx + 2
            break

    # Caso A: Cambió a Crédito y no existía registro previo
    if nuevo_tipo_pago == "Crédito" and fila_credito_idx == -1:
        num_factura = venta_actual[COL_VENTAS["FACTURA"]]
        fecha_venta = venta_actual[COL_VENTAS["FECHA"]]
        vendedor = venta_actual[COL_VENTAS["VENDEDOR"]]
        total = venta_actual[COL_VENTAS["TOTAL"]]
        
        nuevo_credito = [[venta_id, num_factura, fecha_venta, nuevo_cliente, vendedor, total, "Pendiente"]]
        sheets.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Creditos!A:G",
            valueInputOption="USER_ENTERED",
            body={"values": nuevo_credito}
        ).execute()

    # Caso B: Sigue siendo Crédito y ya existía -> Actualizar nombre de cliente
    elif nuevo_tipo_pago == "Crédito" and fila_credito_idx != -1:
        sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"Creditos!D{fila_credito_idx}",
            valueInputOption="USER_ENTERED",
            body={"values": [[nuevo_cliente]]}
        ).execute()

    # Caso C: Cambió a Contado pero existía un registro en Créditos -> Marcar como Pagado
    elif nuevo_tipo_pago == "Contado" and fila_credito_idx != -1:
        sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"Creditos!G{fila_credito_idx}",
            valueInputOption="USER_ENTERED",
            body={"values": [["Pagado"]]}
        ).execute()

    return {"status": "ok", "mensaje": "Detalles de venta actualizados correctamente."}

# ---------------------------------------------------------
# OTROS ENDPOINTS (VENTAS)
# ---------------------------------------------------------
@app.get("/api/ventas/mis-ventas")
def mis_ventas(usuario: dict = Depends(verificar_token)):
    sheets = obtener_servicio_sheets()
    res = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range="Ventas!A2:I").execute()
    filas = res.get('values', [])
    
    ventas = []
    for f in filas:
        if f and len(f) > COL_VENTAS["VENDEDOR"] and f[COL_VENTAS["VENDEDOR"]] == usuario["usuario"]:
            ventas.append({
                "id": f[COL_VENTAS["ID"]],
                "factura": f[COL_VENTAS["FACTURA"]],
                "fecha": f[COL_VENTAS["FECHA"]],
                "cliente": f[COL_VENTAS["CLIENTE"]],
                "tipo_pago": f[COL_VENTAS["TIPO_PAGO"]],
                "total": float(f[COL_VENTAS["TOTAL"]]) if len(f) > COL_VENTAS["TOTAL"] else 0,
                "detalles": json.loads(f[COL_VENTAS["DETALLES"]]) if len(f) > COL_VENTAS["DETALLES"] else []
            })
    return ventas
