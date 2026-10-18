"""Configuración central. Todo sale de variables de entorno (Render → Environment)."""
import os
import secrets
import logging

log = logging.getLogger("cafe0808")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(ROOT_DIR, "static")
LANDING_DIR = os.path.join(ROOT_DIR, "landing")
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "gestion_cafe")
MONGO_POOL_SIZE = int(os.getenv("MONGO_POOL_SIZE", "50"))

# Clave para firmar las sesiones. En producción DEBE estar definida y ser fija:
# si cambia, todas las sesiones abiertas se cierran.
SECRET_KEY = os.getenv("SECRET_KEY") or ""
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(48)
    log.warning("SECRET_KEY no está definida: se generó una temporal. "
                "Las sesiones se cerrarán en cada reinicio. Defínela en Render.")

SESSION_COOKIE = "sesion_0808"
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))

# En local (http) la cookie no puede ser 'Secure'. En Render siempre es https.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1" if os.getenv("RENDER") else "0") == "1"

# Contraseña inicial del admin SOLO si la base de datos no tiene ningún usuario.
ADMIN_INITIAL_PASSWORD = os.getenv("ADMIN_PASSWORD", "0808cafe")

# Documentación de la API (/docs). Apagada salvo que se pida.
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "0") == "1"

# Límites anti-abuso
LOGIN_MAX_FALLOS = 5            # intentos fallidos permitidos...
LOGIN_BLOQUEO_SEG = 5 * 60      # ...antes de bloquear este tiempo
API_REQ_POR_MINUTO = int(os.getenv("API_REQ_POR_MINUTO", "240"))  # por IP
