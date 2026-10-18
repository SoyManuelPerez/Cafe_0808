/* Sesión: login, logout y permisos.
   El navegador NO guarda el usuario ni el rol: se pregunta al servidor (/api/me), que lo lee
   de la base de datos. Cambiar variables desde la consola solo cambia lo que se ve; la API
   rechaza cualquier acción para la que el usuario no tenga permiso. */

function mostrarLogin(mensaje = '') {
    document.body.classList.add('sin-sesion');
    document.body.classList.remove('es-admin');
    document.getElementById('login-screen').style.display = 'flex';
    const aviso = document.getElementById('login-error');
    if (aviso) {
        aviso.textContent = mensaje;
        aviso.hidden = !mensaje;
    }
}

function entrarAlSistema(datos) {
    const usuarioAnterior = usuarioActual;
    usuarioActual = datos.username;
    rolActual = datos.rol;
    // Si entra otra persona en el mismo navegador, se recarga para no mostrar datos del anterior.
    if (usuarioAnterior && usuarioAnterior !== usuarioActual) {
        location.reload();
        return;
    }
    document.body.classList.remove('sin-sesion');
    document.getElementById('login-screen').style.display = 'none';
    aplicarPermisosUI();
    cargarVentasData();
}

async function verificarSesionActiva() {
    // Limpia datos que guardaba la versión anterior (ya no se usan)
    try { ['user_0808', 'rol_0808', 'login_timestamp_0808'].forEach(k => localStorage.removeItem(k)); } catch (_) {}
    try {
        const res = await fetch('/api/me');
        if (res.ok) {
            entrarAlSistema(await res.json());
            return true;
        }
    } catch (err) {
        console.error('No se pudo verificar la sesión:', err);
    }
    mostrarLogin();
    return false;
}

function aplicarPermisosUI() {
    const labelUser = document.getElementById('lbl-user-info');
    if (labelUser) {
        labelUser.textContent = `${usuarioActual} · ${rolActual === 'admin' ? 'Administrador' : 'Ventas'}`;
    }
    const esAdmin = rolActual === 'admin';
    document.body.classList.toggle('es-admin', esAdmin);
    document.querySelectorAll('.admin-only').forEach(el => { el.style.display = esAdmin ? '' : 'none'; });
    if (!esAdmin) {
        const secActiva = document.querySelector('.section.active');
        if (secActiva && secActiva.classList.contains('admin-only')) showSection('ventas');
    }
}

async function ejecutarLogin(e) {
    e.preventDefault();
    const boton = e.target.querySelector('button[type="submit"]');
    const u = document.getElementById('login-user').value;
    const p = document.getElementById('login-pass').value;
    if (boton) boton.disabled = true;

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: u, password: p })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            document.getElementById('login-pass').value = '';
            entrarAlSistema(data);
        } else {
            mostrarLogin(typeof data.detail === 'string' ? data.detail : 'Usuario o contraseña incorrectos');
        }
    } catch (err) {
        mostrarLogin('No hay conexión con el servidor. Revisa tu internet e intenta de nuevo.');
    } finally {
        if (boton) boton.disabled = false;
    }
}

async function ejecutarLogout() {
    try { await fetch('/api/logout', { method: 'POST' }); } catch (_) {}
    // Recargar borra de memoria todos los datos cargados por este usuario.
    location.reload();
}
