from pydantic import BaseModel, Field
from typing import List, Optional

class CompraCreate(BaseModel):
    fecha: str
    libras: float = Field(gt=0)
    costo_total: float = Field(gt=0)
    producto_id: Optional[str] = None

class CompraEmpaqueCreate(BaseModel):
    fecha: str
    tipo_empaque: str  # "bolsa_250g", "bolsa_500g", "etiqueta_250g", "etiqueta_500g"
    cantidad: int = Field(gt=0)
    costo_total: float = Field(gt=0)

class ProductoCreate(BaseModel):
    nombre: str
    gramaje: float = Field(gt=0)
    precio_venta: float = Field(ge=0)
    costo_por_libra: Optional[float] = 0.0

class ProductoUpdate(BaseModel):
    nombre: str
    precio_venta: float = Field(ge=0)

class ClienteCreate(BaseModel):
    nombre: str
    celular: Optional[str] = ""

class ItemVenta(BaseModel):
    producto_id: str
    nombre: str
    gramaje: float
    cantidad: int = Field(gt=0)
    descuento: Optional[float] = 0.0
    presentacion: Optional[str] = "Grano"  # "Grano" o "Molido"
    gramos_totales: float
    precio_unitario: float
    subtotal: float

class VentaCreate(BaseModel):
    fecha: str
    cliente: Optional[str] = "Cliente General"
    tipo_pago: str
    tipo_venta: Optional[str] = "Normal"
    items: List[ItemVenta]
