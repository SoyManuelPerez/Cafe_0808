"""Páginas: landing pública en / y sistema en /sistema/."""
import os

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import LANDING_DIR, ROOT_DIR, TEMPLATES_DIR

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Cambia este número al publicar cambios de CSS/JS para que los navegadores no usen la copia vieja.
VERSION_ASSETS = "3.0.0"


@router.get("/")
def landing():
    return FileResponse(os.path.join(LANDING_DIR, "index.html"), headers={"Cache-Control": "public, max-age=300"})


@router.get("/robots.txt")
def robots():
    return Response(content="User-agent: *\nAllow: /\nDisallow: /sistema\nDisallow: /api\n", media_type="text/plain")


@router.get("/sistema/")
def sistema(request: Request):
    resp = templates.TemplateResponse(request=request, name="sistema.html", context={"v": VERSION_ASSETS})
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# El service worker vive dentro de /sistema/ para no afectar la landing
@router.get("/sistema/sw.js")
def sistema_sw():
    return FileResponse(os.path.join(ROOT_DIR, "sw.js"), media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


# /Sistema, /SISTEMA, /sistema (sin barra) -> /sistema/  (se registra al final)
@router.get("/{ruta:path}")
def atrapa_todo(ruta: str):
    if ruta.strip("/").lower() == "sistema":
        return RedirectResponse(url="/sistema/", status_code=307)
    raise HTTPException(status_code=404, detail="No encontrado")
