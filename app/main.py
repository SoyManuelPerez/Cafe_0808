// Cargar las marcas de café en el selector de descuento
async function cargarOpcionesDescuento() {
    try {
        const res = await fetch('/api/productos/unicos');
        if (!res.ok) return;
        const productos = await res.json();
        
        const select = document.getElementById('descuento-producto');
        select.innerHTML = '<option value="">Seleccione el café a descontar...</option>';
        productos.forEach(p => {
            select.innerHTML += `<option value="${p.nombre}">${p.nombre}</option>`;
        });
    } catch (err) {
        console.error("Error al cargar productos para descuento:", err);
    }
}

// Ejecutar descuento manual en la base de datos MongoDB
async function ejecutarDescuentoManual() {
    const nombre = document.getElementById('descuento-producto').value;
    const libras = parseFloat(document.getElementById('descuento-libras').value);

    if (!nombre || isNaN(libras) || libras <= 0) {
        alert("Por favor seleccione un café e ingrese una cantidad de libras válida.");
        return;
    }

    if (!confirm(`¿Confirma el descuento manual de ${libras} lbs de "${nombre}"?`)) return;

    try {
        const res = await fetch('/api/inventario/descontar-manual', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre: nombre, libras: libras })
        });

        const data = await res.json();
        if (res.ok) {
            alert(data.mensaje);
            document.getElementById('descuento-libras').value = '';
            if (typeof cargarInventario === 'function') cargarInventario();
        } else {
            alert(data.detail || "Error al aplicar el descuento.");
        }
    } catch (err) {
        console.error("Error al descontar stock:", err);
        alert("Ocurrió un error al intentar actualizar el inventario.");
    }
}

// Modal de edición de ventas
function abrirModalEditarVenta(ventaId, clienteActual, tipoPagoActual) {
    document.getElementById('edit-venta-id').value = ventaId;
    document.getElementById('edit-venta-cliente').value = clienteActual || '';
    
    const selectPago = document.getElementById('edit-venta-pago');
    selectPago.value = (tipoPagoActual === 'Efectivo') ? 'Contado' : (tipoPagoActual || 'Contado');

    document.getElementById('modal-editar-venta').style.display = 'flex';
}

function cerrarModalEditarVenta() {
    document.getElementById('modal-editar-venta').style.display = 'none';
    document.getElementById('edit-venta-id').value = '';
}

// Enviar cambios de la venta al servidor
async function guardarCambiosVenta() {
    const ventaId = document.getElementById('edit-venta-id').value;
    const nuevoCliente = document.getElementById('edit-venta-cliente').value.trim();
    const nuevoTipoPago = document.getElementById('edit-venta-pago').value;

    if (!nuevoCliente) {
        alert("El nombre del cliente no puede estar vacío.");
        return;
    }

    try {
        const res = await fetch(`/api/ventas/${ventaId}/editar-detalles`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cliente: nuevoCliente,
                tipo_pago: nuevoTipoPago
            })
        });

        const data = await res.json();
        if (res.ok) {
            alert(data.mensaje);
            cerrarModalEditarVenta();
            if (typeof cargarVentas === 'function') cargarVentas();
        } else {
            alert(data.detail || "Error al actualizar la venta.");
        }
    } catch (err) {
        console.error("Error al editar venta:", err);
        alert("Ocurrió un error de conexión.");
    }
}

// Inicialización de selectores
document.addEventListener('DOMContentLoaded', () => {
    cargarOpcionesDescuento();
});
