from pydantic import BaseModel
from typing import List, Optional

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    rol: Optional[str] = "ventas"  # "admin" o "ventas"

class UserUpdate(BaseModel):
    username: str
    password: Optional[str] = None
    rol: Optional[str] = None

class ClienteCreate(BaseModel):
    nombre: str
    celular: Optional[str] = None

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

class ProductoCreate(BaseModel):
    nombre: str
    gramaje: float
    precio_venta: float
    costo_por_libra: Optional[float] = 0.0

class ProductoUpdate(BaseModel):
    nombre: str
    precio_venta: float

class ItemVenta(BaseModel):
    producto_id: str
    nombre: str
    gramaje: float
    cantidad: int
    descuento: Optional[float] = 0.0
    presentacion: Optional[str] = "Grano"
    gramos_totales: float
    precio_unitario: float
    subtotal: float

class VentaCreate(BaseModel):
    fecha: str
    cliente: str
    tipo_pago: str
    tipo_venta: Optional[str] = "Normal"
    vendedor: Optional[str] = None
    items: List[ItemVenta]
