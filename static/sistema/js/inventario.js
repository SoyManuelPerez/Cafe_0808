/* Productos, existencias y ajustes manuales de inventario */

async function cargarOpcionesDescuento() {
    try {
        const res = await fetch('/api/productos/unicos');
        if (!res.ok) return;
        const productos = await res.json();
        
        const select = document.getElementById('descuento-producto');
        if (!select) return;
        select.innerHTML = '<option value="">Seleccione el café...</option>';
        productos.forEach(p => {
            select.innerHTML += `<option value="${p.nombre}">${p.nombre}</option>`;
        });
        mostrarStockAjuste();
    } catch (err) {
        console.error("Error al cargar productos para descuento:", err);
    }
}

let stockAjusteCache = [];

async function mostrarStockAjuste() {
    const nombre = document.getElementById('descuento-producto').value;
    const cont = document.getElementById('ajuste-stock-actual');
    if (!cont) return;
    if (!nombre) { cont.innerText = ''; return; }
    try {
        const res = await fetch('/api/inventario/resumen');
        const data = await res.json();
        stockAjusteCache = Array.isArray(data.productos_stock) ? data.productos_stock : [];
        const item = stockAjusteCache.find(s => s.nombre === nombre);
        cont.innerText = item ? `Stock actual de "${nombre}": ${item.libras_disponibles} lbs` : '';
    } catch (e) { cont.innerText = ''; }
}

async function ejecutarAjusteInventario() {
    const nombre = document.getElementById('descuento-producto').value;
    const libras = parseFloat(document.getElementById('descuento-libras').value);
    const tipo = document.getElementById('ajuste-tipo').value;
    const motivo = document.getElementById('ajuste-motivo').value.trim();

    if (!nombre || isNaN(libras) || libras <= 0) {
        alert("Por favor seleccione un café e ingrese una cantidad de libras válida.");
        return;
    }

    const verbo = tipo === 'entrada' ? 'AGREGAR' : 'DESCONTAR';
    if (!confirm(`¿Confirma ${verbo} ${libras} lbs de "${nombre}"?\n\nEsto NO se registra como compra y no afecta costos ni ganancias.`)) return;

    try {
        const res = await fetch('/api/inventario/ajustar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre: nombre, libras: libras, tipo: tipo, motivo: motivo })
        });

        const data = await res.json();
        if (res.ok) {
            alert(data.mensaje);
            document.getElementById('descuento-libras').value = '';
            document.getElementById('ajuste-motivo').value = '';
            mostrarStockAjuste();
            cargarHistorialAjustes();
        } else {
            alert(data.detail || "Error al aplicar el ajuste.");
        }
    } catch (err) {
        console.error("Error al ajustar inventario:", err);
        alert("Ocurrió un error al intentar actualizar el inventario.");
    }
}

async function cargarHistorialAjustes() {
    try {
        const res = await fetch('/api/inventario/ajustes');
        if (!res.ok) return;
        const ajustes = await res.json();
        renderTablaPaginada('tabla-ajustes-inventario', Array.isArray(ajustes) ? ajustes : [], a => {
            const esEntrada = a.tipo === 'entrada';
            const color = esEntrada ? '#2ecc71' : '#ff6b6b';
            const lbs = Math.abs(Number(a.libras) || 0);
            return `
                <tr>
                    <td>${a.fecha || ''}</td>
                    <td><strong>${a.producto_nombre || ''}</strong></td>
                    <td style="color:${color}; font-weight:bold;">${esEntrada ? '➕ Entrada' : '➖ Salida'}</td>
                    <td>${lbs.toLocaleString('es-CO')} Lbs</td>
                    <td>${a.motivo || ''}</td>
                    <td>${a.usuario || ''}</td>
                </tr>
            `;
        });
    } catch (err) {
        console.error("Error cargando historial de ajustes:", err);
    }
}

async function cargarTablaExistencias() {
    try {
        const resResumen = await fetch('/api/inventario/resumen');
        const dataResumen = await resResumen.json();

        renderTablaPaginada('tabla-existencias', productosUnicos, p => {
            const stockList = Array.isArray(dataResumen?.productos_stock) ? dataResumen.productos_stock : [];
            const itemStock = stockList.find(s => s.nombre === p.nombre);
            const totalLbs = itemStock ? itemStock.libras_disponibles : 0;
            const pId = p.id || p._id || '';

            return `
                <tr>
                    <td><strong>${p.nombre}</strong></td>
                    <td>${totalLbs} Lbs</td>
                    <td>
                        <input type="number" id="costo-edit-${pId}" value="${p.costo_por_libra || 0}" style="width: 120px;">
                    </td>
                    <td>
                        <button class="btn-gold" style="padding: 4px 8px;" onclick="guardarCostoManual('${p.nombre}', '${pId}')">💾 Guardar Costo</button>
                    </td>
                </tr>
            `;
        });
    } catch (err) {
        console.error("Error cargando existencias:", err);
    }
}

async function guardarCostoManual(nombre, id) {
    const nuevoCosto = parseFloat(document.getElementById(`costo-edit-${id}`).value) || 0;
    
    const res = await fetch('/api/productos/actualizar-costo-libra', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre: nombre, costo_por_libra: nuevoCosto })
    });

    if (res.ok) {
        alert(`Costo actualizado para "${nombre}"`);
        cargarModuloCompras();
    }
}

async function guardarProducto(e) {
    e.preventDefault();
    const payload = {
        nombre: document.getElementById('prod-nombre').value,
        gramaje: parseFloat(document.getElementById('prod-gramos').value),
        precio_venta: parseFloat(document.getElementById('prod-precio').value)
    };

    const res = await fetch('/api/productos', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        alert('Producto creado con éxito');
        document.getElementById('form-producto').reset();
        cargarProductos();
        cargarOpcionesDescuento();
    }
}

async function cargarProductos() {
    try {
        const res = await fetch('/api/productos');
        productosCache = await res.json();
        ordenarProductosArray(productosCache);

        renderTablaPaginada('tabla-productos', productosCache, p => {
            const pId = p.id || p._id || '';
            return `<tr>
                <td><input type="text" id="edit-nom-${pId}" value="${p.nombre}" style="width: 180px;"></td>
                <td>${p.gramaje || 0}g</td>
                <td><input type="number" id="edit-prec-${pId}" value="${p.precio_venta || 0}" style="width: 120px;"></td>
                <td>
                    <button class="btn-gold" style="padding: 4px 8px;" onclick="guardarEdicionProducto('${pId}')">✏️ Guardar</button>
                    <button class="btn-danger" style="padding: 4px 8px;" onclick="eliminarProducto('${pId}')">❌</button>
                </td>
            </tr>`;
        });
    } catch (err) {
        console.error("Error cargando productos:", err);
    }
}

async function guardarEdicionProducto(id) {
    const nuevoNombre = document.getElementById(`edit-nom-${id}`).value;
    const nuevoPrecio = parseFloat(document.getElementById(`edit-prec-${id}`).value);

    if (!nuevoNombre || isNaN(nuevoPrecio)) return alert('Ingrese un nombre y precio válidos');

    const res = await fetch('/api/productos/' + id, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre: nuevoNombre, precio_venta: nuevoPrecio })
    });

    if (res.ok) {
        alert('Producto actualizado correctamente');
        cargarProductos();
        cargarOpcionesDescuento();
    }
}

async function eliminarProducto(id) {
    const res = await fetch('/api/productos/' + id, { method: 'DELETE' });
    if(!res.ok) alert((await res.json()).detail);
    cargarProductos();
    cargarOpcionesDescuento();
}
