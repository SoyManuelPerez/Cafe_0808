/* Compras de café */

async function cargarModuloCompras() {
    try {
        const res = await fetch('/api/productos/unicos');
        productosUnicos = await res.json();
        
        const select = document.getElementById('compra-producto-id');
        const list = Array.isArray(productosUnicos) ? productosUnicos : [];
        select.innerHTML = '<option value="">-- Seleccionar Producto --</option>' + 
            list.map(p => {
                const pId = p.id || p._id;
                return `<option value="${pId}">${p.nombre}</option>`;
            }).join('');

        cargarTablaExistencias();
    } catch (err) {
        console.error("Error cargando compras:", err);
    }
}

function calcularCostoPorLibra() {
    const libras = parseFloat(document.getElementById('compra-libras').value) || 0;
    const costo = parseFloat(document.getElementById('compra-costo').value) || 0;
    const costoPorLibra = libras > 0 ? (costo / libras) : 0;
    
    document.getElementById('costo-libra-calculado').innerText = fmtCOP(costoPorLibra);
}

async function guardarCompra(e) {
    e.preventDefault();
    const prodId = document.getElementById('compra-producto-id').value;
    const libras = parseFloat(document.getElementById('compra-libras').value);
    const costoTotal = parseFloat(document.getElementById('compra-costo').value);

    const payload = {
        fecha: document.getElementById('compra-fecha').value || new Date().toISOString().split('T')[0],
        libras: libras,
        costo_total: costoTotal,
        producto_id: prodId || null
    };

    const res = await fetch('/api/compras', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        alert('Compra de café registrada con éxito');
        document.getElementById('form-compra').reset();
        document.getElementById('costo-libra-calculado').innerText = '$0';
        cargarModuloCompras();
    }
}
