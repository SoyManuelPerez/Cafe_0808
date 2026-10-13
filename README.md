# 0808 Café — Landing + Sistema de inventario

Un solo servicio (FastAPI) con dos caras:

| URL | Qué muestra |
|---|---|
| `/` | Landing pública (carpeta `landing/`) |
| `/sistema/` | Login y sistema de inventario (`templates/index.html`) |
| `/Sistema`, `/SISTEMA`, `/sistema` | Redirigen a `/sistema/` |
| `/api/...` | API del sistema (la usa el sistema, no la landing) |

## Estructura
- `landing/index.html` y `landing/img/` → la landing (editar aquí textos, precios, número de WhatsApp).
- `templates/index.html` → pantalla del sistema.
- `app/main.py` → rutas y API.

## Render
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Variables de entorno:** `MONGO_URI` (obligatoria), `DB_NAME` (opcional, por defecto `gestion_cafe`).
- Dominio propio: Settings → Custom Domains del servicio.

## Local
```
pip install -r requirements.txt
set MONGO_URI=mongodb://localhost:27017   (Windows)  /  export MONGO_URI=...  (Mac/Linux)
uvicorn app.main:app --reload
```
Landing: http://localhost:8000/ — Sistema: http://localhost:8000/sistema/
