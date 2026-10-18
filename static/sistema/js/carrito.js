/* Carritos de venta y de pedido */

function toggleTipoVenta(modo = 'venta') {
    const esCot = modo === 'cotizacion';
    const suffixSelect = esCot ? 'tipo-cot' : 'tipo-venta';
    const suffixDiv = esCot ? 'div-metodo-pago-cot' : 'div-metodo-pago';
    const targetCarrito = esCot ? carritoCotizacion : carrito;

    const tipo = document.getElementById(suffixSelect).value;
    const divPago = document.getElementById(suffixDiv);
    if (divPago) divPago.style.display = (tipo === 'Obsequio') ? 'none' : 'block';
    
    if (tipo === 'Venta al Costo') {
        aplicarPreciosAlCostoCarrito(modo);
    } else if (tipo === 'Normal') {
        targetCarrito.forEach(item => {
            const prod = productosCache.find(p => String(p.id || p._id) === String(item.producto_id));
            if (prod) {
                item.precio_unitario = prod.precio_venta || 0;
                item.subtotal = Math.max(0, (item.precio_unitario * item.cantidad) - ((item.descuento || 0) * item.cantidad));
            }
        });
        renderCarrito(modo);
    } else {
        renderCarrito(modo);
    }
}

async function aplicarPreciosAlCostoCarrito(modo = 'venta') {
    const esCot = modo === 'cotizacion';
    const targetCarrito = esCot ? carritoCotizacion : carrito;

    try {
        const resEmp = await fetch('/api/empaques/resumen');
        const resumenEmp = await resEmp.json();

        targetCarrito.forEach(item => {
            const prod = productosCache.find(p => String(p.id || p._id) === String(item.producto_id));
            const costoLibra = prod ? (prod.costo_por_libra || 0) : 0;
            const costoGramo = costoLibra / 500.0;
            const costoCafeUnitario = (item.gramaje || 0) * costoGramo;

            let costoEmpaqueUnitario = 0;
            if (item.gramaje === 250) {
                costoEmpaqueUnitario = (resumenEmp["bolsa_250g"]?.costo_unitario || 0) + (resumenEmp["etiqueta_250g"]?.costo_unitario || 0);
            } else if (item.gramaje === 500) {
                costoEmpaqueUnitario = (resumenEmp["bolsa_500g"]?.costo_unitario || 0) + (resumenEmp["etiqueta_500g"]?.costo_unitario || 0);
            } else if (item.gramaje === 2500) {
                costoEmpaqueUnitario = (resumenEmp["etiqueta_500g"]?.costo_unitario || 0);
            }

            const costoTotalUnitario = Math.round(costoCafeUnitario + costoEmpaqueUnitario);
            item.precio_unitario = costoTotalUnitario;
            item.subtotal = Math.max(0, (costoTotalUnitario * item.cantidad) - ((item.descuento || 0) * item.cantidad));
        });

        renderCarrito(modo);
    } catch (err) {
        console.error("Error al calcular precios al costo:", err);
    }
}

function agregarAlCarrito(modo) {
    const esCot = modo === 'cotizacion';
    const suffix = esCot ? '-cot' : '';

    const pId = document.getElementById('select-producto' + suffix).value;
    const cant = parseInt(document.getElementById('cant-producto' + suffix).value) || 1;
    const descuento = parseFloat(document.getElementById('desc-producto' + suffix).value) || 0;
    const pres = document.getElementById('pres-producto' + suffix).value || 'Grano';
    const prod = productosCache.find(p => String(p.id || p._id) === String(pId));

    if (!prod) return alert('Seleccione un producto válido');

    const prodIdFinal = prod.id || prod._id;
    const selectTipo = document.getElementById(esCot ? 'tipo-cot' : 'tipo-venta');
    const tipoVenta = selectTipo ? selectTipo.value : 'Normal';
    
    let precioBase = prod.precio_venta || 0;

    if (tipoVenta === 'Venta al Costo') {
        const costoLibra = prod.costo_por_libra || 0;
        const costoGramo = costoLibra / 500.0;
        precioBase = Math.round((prod.gramaje || 0) * costoGramo);
    }

    const subtotalCalculado = Math.max(0, (precioBase * cant) - (descuento * cant));
    const targetCarrito = esCot ? carritoCotizacion : carrito;

    const indexExistente = targetCarrito.findIndex(item => String(item.producto_id) === String(prodIdFinal) && item.descuento === descuento && item.presentacion === pres);
    
    if (indexExistente !== -1) {
        targetCarrito[indexExistente].cantidad += cant;
        targetCarrito[indexExistente].gramos_totales = targetCarrito[indexExistente].gramaje * targetCarrito[indexExistente].cantidad;
        targetCarrito[indexExistente].subtotal = Math.max(0, (targetCarrito[indexExistente].precio_unitario * targetCarrito[indexExistente].cantidad) - (descuento * targetCarrito[indexExistente].cantidad));
    } else {
        targetCarrito.push({
            producto_id: prodIdFinal,
            nombre: prod.nombre,
            gramaje: prod.gramaje || 0,
            cantidad: cant,
            valor_add: 0,
            descuento: descuento,
            presentacion: pres,
            gramos_totales: (prod.gramaje || 0) * cant,
            precio_unitario: precioBase,
            subtotal: subtotalCalculado
        });
    }

    document.getElementById('cant-producto' + suffix).value = 1;
    document.getElementById('desc-producto' + suffix).value = 0;

    if (tipoVenta === 'Venta al Costo') {
        aplicarPreciosAlCostoCarrito(modo);
    } else {
        renderCarrito(modo);
    }
}

function actualizarPrecioEnCarrito(index, modo, nuevoPrecioStr) {
    const esCot = modo === 'cotizacion';
    const targetCarrito = esCot ? carritoCotizacion : carrito;
    
    const nuevoPrecio = parseFloat(nuevoPrecioStr);
    if (isNaN(nuevoPrecio) || nuevoPrecio < 0) return;

    const item = targetCarrito[index];
    if (item) {
        item.precio_unitario = nuevoPrecio;
        item.subtotal = Math.max(0, (nuevoPrecio * item.cantidad) - ((item.descuento || 0) * item.cantidad));
        renderCarrito(modo);
    }
}

function actualizarCantidadEnCarrito(index, modo, valorStr) {
    const target = modo === 'cotizacion' ? carritoCotizacion : carrito;
    const item = target[index];
    const cant = parseInt(valorStr, 10);
    if (!item) return;
    if (isNaN(cant) || cant < 1) { renderCarrito(modo); return; }
    item.cantidad = cant;
    item.gramos_totales = (item.gramaje || 0) * cant;
    item.subtotal = Math.max(0, ((item.precio_unitario || 0) - (item.descuento || 0)) * cant);
    renderCarrito(modo);
}

function actualizarDescuentoEnCarrito(index, modo, valorStr) {
    const target = modo === 'cotizacion' ? carritoCotizacion : carrito;
    const item = target[index];
    const desc = parseFloat(valorStr);
    if (!item) return;
    if (isNaN(desc) || desc < 0) { renderCarrito(modo); return; }
    item.descuento = desc;
    item.subtotal = Math.max(0, ((item.precio_unitario || 0) - desc) * item.cantidad);
    renderCarrito(modo);
}

function quitarDelCarrito(index, modo) {
    if(modo === 'cotizacion') {
        carritoCotizacion.splice(index, 1);
    } else {
        carrito.splice(index, 1);
    }
    renderCarrito(modo);
}

function vaciarCarrito(modo) {
    const target = modo === 'cotizacion' ? carritoCotizacion : carrito;
    if (target.length === 0) return;
    if (confirm('¿Vaciar carrito?')) {
        if(modo === 'cotizacion') carritoCotizacion = [];
        else carrito = [];
        renderCarrito(modo);
    }
}

function renderCarrito(modo) {
    const esCot = modo === 'cotizacion';
    const targetCarrito = esCot ? carritoCotizacion : carrito;
    const tbody = document.querySelector(esCot ? '#tabla-carrito-cot tbody' : '#tabla-carrito tbody');
    const selectTipo = document.getElementById(esCot ? 'tipo-cot' : 'tipo-venta');
    const esObsequio = selectTipo && selectTipo.value === 'Obsequio';
    let total = 0;

    if (tbody) {
        tbody.innerHTML = targetCarrito.map((i, index) => {
            const sub = esObsequio ? 0 : i.subtotal;
            total += sub;
            return `
                <tr>
                    <td>${i.nombre}</td>
                    <td><strong>${i.presentacion}</strong></td>
                    <td>${i.gramaje}g</td>
                    <td>
                        ${esObsequio ? '$0' : `<input type="number" class="input-cart-price" value="${i.precio_unitario}" min="0" step="100" onchange="actualizarPrecioEnCarrito(${index}, '${modo}', this.value)">`}
                    </td>
                    <td><input type="number" class="input-cart-price" style="width:70px;" value="${i.cantidad}" min="1" step="1" onchange="actualizarCantidadEnCarrito(${index}, '${modo}', this.value)"></td>
                    <td>${esObsequio ? '$0' : `<input type="number" class="input-cart-price" style="width:90px;" value="${i.descuento || 0}" min="0" step="100" onchange="actualizarDescuentoEnCarrito(${index}, '${modo}', this.value)">`}</td>
                    <td>${fmtCOP(sub)}</td>
                    <td><button class="btn-danger" onclick="quitarDelCarrito(${index}, '${modo}')">❌ Quitar</button></td>
                </tr>
            `;
        }).join('');
    }

    const txtTotal = document.getElementById(esCot ? 'total-carrito-txt-cot' : 'total-carrito-txt');
    if (txtTotal) txtTotal.innerText = fmtCOP(total);
}

async function procesarVenta() {
    if (carrito.length === 0) return alert('El carrito está vacío');

    const clienteInput = document.getElementById('select-cliente-venta').value.trim();
    const clienteFinal = clienteInput || 'Cliente General';

    const tipoVenta = document.getElementById('tipo-venta').value;
    const payload = {
        fecha: new Date().toISOString().split('T')[0],
        cliente: clienteFinal,
        vendedor: usuarioActual,
        tipo_pago: tipoVenta === 'Obsequio' ? 'N/A' : document.getElementById('pago-venta').value,
        tipo_venta: tipoVenta,
        items: carrito
    };

    const res = await fetch('/api/ventas', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        const data = await res.json();
        if (data.estado_despacho === 'Pendiente') {
            alert('⚠️ Advertencia: No hay suficiente stock/empaques. La venta se registró con éxito como Venta Parcial (Pendiente).');
        } else {
            alert(tipoVenta === 'Obsequio' ? 'Obsequio registrado' : (tipoVenta === 'Venta al Costo' ? 'Venta al costo procesada con éxito' : 'Venta procesada con éxito'));
        }
        carrito = [];
        renderCarrito('venta');
        cargarVentasData();
    } else {
        const err = await res.json();
        alert(err.detail || 'Error al procesar la venta');
    }
}

async function procesarCotizacion() {
    if (carritoCotizacion.length === 0) return alert('El carrito de pedidos está vacío');

    const clienteInput = document.getElementById('select-cliente-cot').value.trim();
    const clienteFinal = clienteInput || 'Cliente General';
    const tipoCot = document.getElementById('tipo-cot').value;

    const payload = {
        fecha: new Date().toISOString().split('T')[0],
        cliente: clienteFinal,
        vendedor: usuarioActual,
        tipo_pago: tipoCot === 'Obsequio' ? 'N/A' : document.getElementById('pago-cot').value,
        tipo_venta: tipoCot,
        items: carritoCotizacion
    };

    // --- MODO EDICIÓN: se actualiza el pedido existente (mismo consecutivo) ---
    if (pedidoEditandoId) {
        const resEdit = await fetch(`/api/cotizaciones/${pedidoEditandoId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if (resEdit.ok) {
            const dataEdit = await resEdit.json();
            alert(`Pedido N° ${dataEdit.consecutivo} actualizado con éxito`);
            cancelarEdicionPedido(true);
            cargarCotizacionesData();
        } else {
            let msg = 'Error al guardar los cambios del pedido';
            try { const err = await resEdit.json(); msg = err.detail || msg; } catch (_) {}
            alert(msg);
            if (resEdit.status === 400 || resEdit.status === 409) cargarMisCotizaciones();
        }
        return;
    }

    const res = await fetch('/api/cotizaciones', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        const data = await res.json();
        alert(`Pedido N° ${data.consecutivo} registrado con éxito`);
        carritoCotizacion = [];
        renderCarrito('cotizacion');
        cargarCotizacionesData();
    } else {
        alert('Error al registrar el pedido');
    }
}
