/* Arranque del sistema: verifica la sesión con el servidor y registra el service worker. */

verificarSesionActiva();

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sistema/sw.js', { scope: '/sistema/' })
            .catch((err) => console.error('Error al registrar Service Worker:', err));
    });
}
