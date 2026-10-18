"""Gestión de usuarios (solo administradores)."""
from fastapi import APIRouter, Depends, HTTPException

from app.database import db, fix_id, oid
from app.models import UserCreate, UserUpdate
from app.security import hash_password, invalidar_sesiones, require_admin
from app.services.inventario import ahora

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"], dependencies=[Depends(require_admin)])


@router.post("", status_code=201)
def crear_usuario(usr: UserCreate):
    username = usr.username.strip()
    if db.usuarios.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe.")
    res = db.usuarios.insert_one({
        "username": username,
        "password_hash": hash_password(usr.password),
        "rol": usr.rol,
        "token_version": 0,
        "creado_en": ahora(),
    })
    return {"id": str(res.inserted_id), "mensaje": "Usuario creado exitosamente"}


@router.get("")
def listar_usuarios():
    usuarios = db.usuarios.find({}, {"password_hash": 0, "token_version": 0}).sort("username", 1)
    return [fix_id(u) for u in usuarios]


@router.put("/{user_id}")
def editar_usuario(user_id: str, usr: UserUpdate, admin: dict = Depends(require_admin)):
    _id = oid(user_id)
    actual = db.usuarios.find_one({"_id": _id})
    if not actual:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    username = usr.username.strip()
    if db.usuarios.find_one({"username": username, "_id": {"$ne": _id}}):
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está en uso.")

    cambios = {"username": username}
    cerrar_sesiones = False
    if usr.password and usr.password.strip():
        if len(usr.password.strip()) < 6:
            raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres.")
        cambios["password_hash"] = hash_password(usr.password)
        cerrar_sesiones = True
    if usr.rol and usr.rol != actual.get("rol"):
        if actual.get("username") == "admin" and usr.rol != "admin":
            raise HTTPException(status_code=400, detail="El usuario 'admin' principal debe seguir siendo administrador.")
        if _id == admin["_id"] and usr.rol != "admin":
            raise HTTPException(status_code=400, detail="No puedes quitarte a ti mismo el rol de administrador.")
        cambios["rol"] = usr.rol
        cerrar_sesiones = True
    if actual.get("username") == "admin" and username != "admin":
        raise HTTPException(status_code=400, detail="No se puede renombrar el usuario 'admin' principal.")

    db.usuarios.update_one({"_id": _id}, {"$set": cambios})
    if cerrar_sesiones and _id != admin["_id"]:
        invalidar_sesiones(_id)
    return {"mensaje": "Usuario actualizado exitosamente"}


@router.delete("/{user_id}")
def eliminar_usuario(user_id: str, admin: dict = Depends(require_admin)):
    _id = oid(user_id)
    usuario = db.usuarios.find_one({"_id": _id})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.get("username") == "admin":
        raise HTTPException(status_code=400, detail="No se puede eliminar el usuario administrador principal ('admin').")
    if _id == admin["_id"]:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propio usuario.")
    db.usuarios.delete_one({"_id": _id})
    return {"mensaje": "Usuario eliminado correctamente"}
