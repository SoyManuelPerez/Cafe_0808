"""Autenticación, roles y límites anti-abuso.

Reglas clave:
- La sesión es una cookie firmada (JWT) HttpOnly: el navegador no puede leerla ni editarla.
- En CADA petición se vuelve a leer el usuario en la base de datos. El rol que vale es el
  de la base de datos, nunca uno enviado por el navegador. Si el usuario se borra, se le
  cambia la contraseña o el rol, la sesión vieja deja de servir al instante.
"""
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response

from app.config import (
    SECRET_KEY, SESSION_COOKIE, SESSION_HOURS, COOKIE_SECURE,
    LOGIN_MAX_FALLOS, LOGIN_BLOQUEO_SEG,
)
from app.database import db, oid

ROLES_VALIDOS = ("admin", "ventas")
_ALGORITMO = "HS256"
# Hash fijo para comparar cuando el usuario no existe (mismo tiempo de respuesta).
_HASH_FALSO = bcrypt.hashpw(b"usuario-inexistente", bcrypt.gensalt()).decode()


# ---------------- Contraseñas ----------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.strip().encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.strip().encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def verificar_credenciales(username: str, password: str):
    user = db.usuarios.find_one({"username": username})
    hash_guardado = user.get("password_hash", "") if user else _HASH_FALSO
    valido = verify_password(password, hash_guardado or _HASH_FALSO)
    return user if (user and valido) else None


# ---------------- Sesión ----------------

def abrir_sesion(response: Response, user: dict):
    ahora = datetime.now(timezone.utc)
    token = jwt.encode({
        "sub": str(user["_id"]),
        "ver": int(user.get("token_version", 0)),
        "iat": ahora,
        "exp": ahora + timedelta(hours=SESSION_HOURS),
    }, SECRET_KEY, algorithm=_ALGORITMO)
    response.set_cookie(
        SESSION_COOKIE, token,
        max_age=SESSION_HOURS * 3600, httponly=True, secure=COOKIE_SECURE,
        samesite="strict", path="/",
    )


def cerrar_sesion(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=COOKIE_SECURE, samesite="strict")
    response.delete_cookie("session_user", path="/")  # cookie antigua (insegura), por si quedó


def invalidar_sesiones(user_id):
    """Cierra todas las sesiones abiertas de un usuario (cambio de clave o de rol)."""
    db.usuarios.update_one({"_id": user_id}, {"$inc": {"token_version": 1}})


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    try:
        datos = jwt.decode(token, SECRET_KEY, algorithms=[_ALGORITMO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Tu sesión venció. Vuelve a iniciar sesión.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Sesión inválida. Vuelve a iniciar sesión.")

    user = db.usuarios.find_one({"_id": oid(datos.get("sub", ""))}, {"password_hash": 0})
    if not user or int(user.get("token_version", 0)) != int(datos.get("ver", -1)):
        raise HTTPException(status_code=401, detail="Tu sesión ya no es válida. Vuelve a iniciar sesión.")

    rol = user.get("rol")
    if rol not in ROLES_VALIDOS:
        raise HTTPException(status_code=403, detail="Tu usuario no tiene un rol válido.")
    return {"id": str(user["_id"]), "_id": user["_id"], "username": user["username"], "rol": rol}


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Esta acción es solo para administradores.")
    return user


def es_admin(user: dict) -> bool:
    return user.get("rol") == "admin"


def exigir_dueno_o_admin(user: dict, doc: dict, campo: str = "vendedor"):
    if not es_admin(user) and doc.get(campo) != user["username"]:
        raise HTTPException(status_code=403, detail="Solo puedes gestionar tus propios registros.")


# ---------------- Límites anti-abuso ----------------

def ip_cliente(request: Request) -> str:
    # Render pone la IP real en X-Forwarded-For (el primer valor)
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


class LimiteVentana:
    """Cuenta peticiones por clave en una ventana de tiempo (memoria del proceso)."""

    def __init__(self, maximo: int, ventana_seg: int):
        self.maximo, self.ventana = maximo, ventana_seg
        self._registros = defaultdict(deque)
        self._lock = threading.Lock()
        self._ultima_limpieza = time.monotonic()

    def permitir(self, clave: str) -> bool:
        ahora = time.monotonic()
        with self._lock:
            q = self._registros[clave]
            while q and ahora - q[0] > self.ventana:
                q.popleft()
            if len(q) >= self.maximo:
                return False
            q.append(ahora)
            if ahora - self._ultima_limpieza > 120:
                self._limpiar(ahora)
            return True

    def _limpiar(self, ahora):
        for k in [k for k, q in self._registros.items() if not q or ahora - q[-1] > self.ventana]:
            del self._registros[k]
        self._ultima_limpieza = ahora


class BloqueoLogin:
    """Tras varios intentos fallidos, bloquea temporalmente ese usuario+IP."""

    def __init__(self):
        self._fallos = {}
        self._lock = threading.Lock()

    def _clave(self, ip, username):
        return f"{ip}|{username.lower()}"

    def segundos_bloqueado(self, ip, username) -> int:
        with self._lock:
            info = self._fallos.get(self._clave(ip, username))
            if info and info["hasta"] > time.monotonic():
                return int(info["hasta"] - time.monotonic()) + 1
            return 0

    def fallo(self, ip, username):
        with self._lock:
            k = self._clave(ip, username)
            info = self._fallos.setdefault(k, {"n": 0, "hasta": 0})
            info["n"] += 1
            if info["n"] >= LOGIN_MAX_FALLOS:
                info["hasta"] = time.monotonic() + LOGIN_BLOQUEO_SEG
                info["n"] = 0
            if len(self._fallos) > 5000:  # evita crecer sin límite
                self._fallos.clear()

    def exito(self, ip, username):
        with self._lock:
            self._fallos.pop(self._clave(ip, username), None)


bloqueo_login = BloqueoLogin()
