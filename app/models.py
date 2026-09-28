from pydantic import BaseModel
from typing import List, Optional

# ==========================================
# MODELOS DE USUARIOS Y AUTENTICACIÓN
# ==========================================

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    rol: Optional[str] = "ventas"

class UserUpdate(BaseModel):
    username: str
    password: Optional[str] = None
    rol: Optional[str] = None


# ==========================================
# MODELO DE CLIENTES
# ==========================================

class ClienteCreate(BaseModel):
    nombre: str
    celular: Optional[str] = None


# ==========================================
# MODELOS DE COMPRAS (INSUMOS Y MATERIA PRIMA)
# ==========================================

class CompraEmpaqueCreate(BaseModel):
    fecha: str
    tipo_empaque: str
    cantidad: int
    costo_total: float

class CompraCreate(BaseModel):
    fecha: str
    libras: float
    costo_total: float
    producto_id: Optional[str] = None


# ==========================================
# MODELOS DE PRODUCTOS E INVENTARIO
# ==========================================

class ProductoCreate(BaseModel):
    nombre: str
    gramaje: float
    precio_venta: float
    costo_por_libra: Optional[float] = 0.0

class ProductoUpdate(BaseModel):
    nombre: str
    precio_venta: float


# ==========================================
# MODELOS DE VENTAS Y PEDIDOS
# ==========================================

class VentaItem(BaseModel):
    producto_id: Optional[str] = None
    nombre: str
    gramaje: int
    cantidad: int
    descuento: float = 0.0
    presentacion: str
    gramos_totales: int
    precio_unitario: float
    subtotal: float

class VentaCreate(BaseModel):
    fecha: str
    cliente: str
    vendedor: Optional[str] = None
    tipo_pago: str
    tipo_venta: str  # Puede ser: "Normal", "Obsequio", "Venta al Costo"
    items: List[VentaItem]
