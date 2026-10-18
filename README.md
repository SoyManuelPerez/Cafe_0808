# 0808 Café — Landing + Sistema de inventario (v3)

Un solo servicio (FastAPI) con dos caras:

| URL | Qué muestra |
|---|---|
| `/` | Landing pública (carpeta `landing/`) |
| `/sistema/` | Login y sistema de inventario |
| `/Sistema`, `/SISTEMA`, `/sistema` | Redirigen a `/sistema/` |
| `/api/...` | API del sistema (requiere sesión, salvo `/api/public/precios`) |

## Estructura

```
app/
  main.py              arma la app (middlewares, rutas, archivos estáticos)
  config.py            variables de entorno
  database.py          conexión única a MongoDB (pool) + índices
  security.py          sesión firmada, roles, contraseñas, bloqueo por intentos
  middleware.py        cabeceras de seguridad, CSRF, límite de peticiones por IP
  models.py            validación de todo lo que llega a la API
  pdf_generator.py     facturas y pedidos en PDF
  services/inventario.py   stock de café y empaques, costos de una venta
  routers/             un archivo por módulo:
    auth.py  usuarios.py  clientes.py  gastos.py  empaques.py
    productos.py  inventario.py  ventas.py  cotizaciones.py
    public.py (precios para la landing)  pages.py (páginas)
templates/sistema.html       pantalla del sistema (solo HTML)
static/sistema/css/          sistema.css (estructura) + tema.css (colores 0808)
static/sistema/js/           un archivo por módulo: core, auth, ventas, carrito,
                             pedidos, clientes, gastos, inventario, empaques,
                             compras, creditos, reportes, usuarios, pdf, app
landing/index.html           landing (solo HTML)
landing/assets/css/          landing.css
landing/assets/js/           config.js (WhatsApp, cafés, precios de respaldo),
                             precios.js, carrito.js, fichas.js, extras.js, main.js
landing/assets/img/          fotos de producto (WebP + JPG) y logos
```

## Precios de la landing
La landing toma el precio del **sistema** cuando el nombre del producto contiene
`bourbon`, `chiroso` o `blend` y el gramaje es 250 o 500. Si no lo encuentra, usa los
precios de respaldo de `landing/assets/js/config.js`. Cambiar un precio en
*Productos e Inventario* lo actualiza en la landing en máximo 1 minuto.

## Seguridad (qué cambió en v3)
- Toda la API exige sesión. Las secciones de administración exigen rol `admin`.
- La sesión es una cookie firmada, `HttpOnly` y `SameSite=Strict`: el navegador no puede
  leerla ni modificarla. El rol se lee **en cada petición desde la base de datos**;
  cambiar el rol o la contraseña de alguien, o borrarlo, corta su sesión al instante.
- Un vendedor solo ve y gestiona sus propias ventas y pedidos, y no ve costos ni ganancias.
- Precios, subtotales y gramos se recalculan en el servidor.
- Bloqueo de 5 minutos tras 5 intentos fallidos de login; límite de peticiones por IP.
- Protección CSRF, cabeceras de seguridad (CSP, HSTS, X-Frame-Options) y `/docs` apagado.

## Render
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 --bind 0.0.0.0:$PORT --timeout 60`
- **Variables de entorno:**
  - `MONGO_URI` (obligatoria)
  - `SECRET_KEY` (**obligatoria**): texto largo y aleatorio. Si falta, las sesiones se cierran en cada reinicio.
    Genera una con: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
  - `DB_NAME` (opcional, por defecto `gestion_cafe`)
  - `WEB_CONCURRENCY` (opcional, procesos; por defecto 2)
  - `ADMIN_PASSWORD` (opcional): contraseña del `admin` **solo** si la base está vacía.
  - `ENABLE_DOCS=1` (opcional): enciende `/docs` para pruebas.

## Local
```
pip install -r requirements.txt
set MONGO_URI=mongodb://localhost:27017      (Windows)
set SECRET_KEY=cualquier-texto-largo
uvicorn app.main:app --reload
```
Landing: http://localhost:8000/ — Sistema: http://localhost:8000/sistema/

Al publicar cambios de CSS/JS del sistema, sube `VERSION_ASSETS` en `app/routers/pages.py`
(y el `?v=` en `landing/index.html` para la landing) para que los navegadores no usen la copia vieja.
