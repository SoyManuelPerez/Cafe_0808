"""Modelos de entrada de la API. Validan tipos, límites y limpian texto antes de guardar."""
import re
from typing import Annotated, List, Optional, Literal

from pydantic import AfterValidator, BaseModel, Field

_ETIQUETAS = re.compile(r"[<>]")


def _limpiar(valor: str) -> str:
    # Quita < y > para que ningún texto guardado pueda inyectar HTML/JS en las pantallas.
    return _ETIQUETAS.sub("", valor).strip()


Texto = Annotated[str, Field(max_length=200), AfterValidator(_limpiar)]
TextoLargo = Annotated[str, Field(max_length=1000), AfterValidator(_limpiar)]
Fecha = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}")]
Dinero = Annotated[float, Field(ge=0, le=1_000_000_000)]


# ==========================================
# USUARIOS Y AUTENTICACIÓN
# ==========================================

class UserLogin(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    username: Annotated[str, Field(min_length=2, max_length=40, pattern=r"^[\w .-]+$")]
    password: str = Field(min_length=6, max_length=128)
    rol: Literal["admin", "ventas"] = "ventas"


class UserUpdate(BaseModel):
    username: Annotated[str, Field(min_length=2, max_length=40, pattern=r"^[\w .-]+$")]
    password: Optional[str] = Field(default=None, max_length=128)
    rol: Optional[Literal["admin", "ventas"]] = None


# ==========================================
# CLIENTES
# ==========================================

class ClienteCreate(BaseModel):
    nombre: Annotated[Texto, Field(min_length=1)]
    celular: Optional[Annotated[str, Field(max_length=30), AfterValidator(_limpiar)]] = None


# ==========================================
# GASTOS
# ==========================================

class GastoCreate(BaseModel):
    monto: Dinero
    fecha: Fecha
    observacion: TextoLargo


# ==========================================
# COMPRAS (INSUMOS Y MATERIA PRIMA)
# ==========================================

class CompraEmpaqueCreate(BaseModel):
    fecha: Fecha
    tipo_empaque: Literal["bolsa_250g", "bolsa_500g", "etiqueta_250g", "etiqueta_500g"]
    cantidad: int = Field(gt=0, le=1_000_000)
    costo_total: Dinero


class CompraCreate(BaseModel):
    fecha: Fecha
    libras: float = Field(gt=0, le=100_000)
    costo_total: Dinero
    producto_id: Optional[str] = Field(default=None, max_length=40)


class AjusteEmpaque(BaseModel):
    tipo_empaque: Literal["bolsa_250g", "bolsa_500g", "etiqueta_250g", "etiqueta_500g"]
    disponibles: int = Field(ge=0, le=10_000_000)
    costo_unitario: Dinero = 0.0


class CostoLibra(BaseModel):
    nombre: Annotated[Texto, Field(min_length=1)]
    costo_por_libra: Dinero


# ==========================================
# PRODUCTOS E INVENTARIO
# ==========================================

class ProductoCreate(BaseModel):
    nombre: Annotated[Texto, Field(min_length=1)]
    gramaje: float = Field(gt=0, le=100_000)
    precio_venta: Dinero
    costo_por_libra: Optional[Dinero] = 0.0


class ProductoUpdate(BaseModel):
    nombre: Annotated[Texto, Field(min_length=1)]
    precio_venta: Dinero


class AjusteInventarioCreate(BaseModel):
    nombre: Texto               # Nombre del café (producto)
    libras: float               # Siempre positivo; el sentido lo da "tipo"
    tipo: str                   # "entrada" (suma stock) o "salida" (descuenta stock)
    motivo: Optional[TextoLargo] = None


class DescuentoManual(BaseModel):
    nombre: Texto
    libras: float
    motivo: Optional[TextoLargo] = None


# ==========================================
# VENTAS Y PEDIDOS
# ==========================================

class VentaItem(BaseModel):
    producto_id: Optional[str] = Field(default=None, max_length=40)
    nombre: Texto
    gramaje: int = Field(gt=0, le=100_000)
    cantidad: int = Field(gt=0, le=10_000)
    descuento: Dinero = 0.0
    presentacion: Texto
    gramos_totales: int = Field(ge=0)
    precio_unitario: Dinero
    subtotal: float = 0.0


class VentaCreate(BaseModel):
    fecha: Fecha
    cliente: Texto
    vendedor: Optional[Texto] = None
    tipo_pago: Texto
    tipo_venta: Texto  # "Normal", "Obsequio", "Venta al Costo"
    items: List[VentaItem] = Field(max_length=200)


class EditarDetallesVenta(BaseModel):
    cliente: Annotated[Texto, Field(min_length=1)]
    tipo_pago: Annotated[Texto, Field(min_length=1)]
