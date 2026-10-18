"""Inicio y cierre de sesión. /api/me dice quién es el usuario según la base de datos."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.models import UserLogin
from app.security import (
    abrir_sesion, bloqueo_login, cerrar_sesion, get_current_user, ip_cliente,
    verificar_credenciales, ROLES_VALIDOS,
)

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login")
def login(user_data: UserLogin, request: Request, response: Response):
    username = user_data.username.strip()
    ip = ip_cliente(request)

    espera = bloqueo_login.segundos_bloqueado(ip, username)
    if espera:
        raise HTTPException(status_code=429, detail=f"Demasiados intentos fallidos. Intenta de nuevo en {espera // 60 + 1} min.")

    user = verificar_credenciales(username, user_data.password)
    if not user or user.get("rol") not in ROLES_VALIDOS:
        bloqueo_login.fallo(ip, username)
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    bloqueo_login.exito(ip, username)
    abrir_sesion(response, user)
    return {"mensaje": "Login exitoso", "username": user["username"], "rol": user["rol"]}


@router.post("/logout")
def logout(response: Response):
    cerrar_sesion(response)
    return {"mensaje": "Sesión cerrada"}


@router.get("/me")
def quien_soy(user: dict = Depends(get_current_user)):
    return {"username": user["username"], "rol": user["rol"]}
