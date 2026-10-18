/* Pedidos (cotizaciones) */

async function cargarCotizacionesData() {
    try {
        const resProds = await fetch('/api/productos');
        productosCache = await resProds.json();
        ordenarProductosArray(productosCache);

        const selectCot = document.getElementById('select-producto-cot');
        if (selectCot) {
            selectCot.innerHTML = productosCache.map(p => {
                const pId = p.id || p._id;
                return `<option value="${pId}">${p.nombre} (${p.gramaje || 0}g) - ${fmtCOP(p.precio_venta)}</option>`;
            }).join('');
        }

        await actualizarAutocompletarClientes();
        cargarMisCotizaciones();
    } catch (err) {
        console.error("Error al cargar pedidos:", err);
    }
}

async function cargarMisCotizaciones() {
    try {
        const res = await fetch('/api/cotizaciones');
        const cotizaciones = await res.json();
        
        const list = Array.isArray(cotizaciones) ? cotizaciones : [];
        cotizacionesCache = list;
        const misCot = (rolActual === 'admin') ? list : list.filter(c => c && c.vendedor === usuarioActual);
           // --- ORDENAR DE MAYOR A MENOR (El más reciente primero, el 0001 al final) ---
            misCot.sort((a, b) => {
                const numA = parseInt(a.consecutivo_str || a.consecutivo || a.id || 0, 10);
                const numB = parseInt(b.consecutivo_str || b.consecutivo || b.id || 0, 10);
                return numB - numA; // De mayor a menor
            });
        renderTablaPaginada('tabla-mis-cotizaciones', misCot, c => {
            try {
                if (!c) return '';
                const idVal = c.id || c._id || '';
                const numCot = c.consecutivo_str || (idVal ? String(idVal).substring(0,8) : 'N/A');
                const estado = c.estado || 'Pendiente';
                const esAnulado = estado === 'Anulado';
                const esDespachado = estado === 'Despachado';

                let badgeEstado = '<span style="color:#2ecc71; font-weight:bold;">📦 Pendiente</span>';
                if (esAnulado) {
                    badgeEstado = '<span style="color:#ff6b6b; font-weight:bold;">🚫 Anulado</span>';
                } else if (esDespachado) {
                    badgeEstado = '<span style="color:#D4AF37; font-weight:bold;">✅ Despachado</span>';
                }

                const estiloFila = esAnulado ? 'style="background-color: rgba(255, 107, 107, 0.15); color: #ff6b6b;"' : '';

                return `
                    <tr ${estiloFila}>
                        <td><strong>${numCot}</strong></td>
                        <td>${c.fecha || ''}</td>
                        <td>${c.cliente || ''}</td>
                        <td><strong>${c.tipo_venta || 'Normal'}</strong></td>
                        <td>${badgeEstado}</td>
                        <td>${fmtCOP(c.total_venta)}</td>
                        <td>
                            ${(!esAnulado && !esDespachado) ? `<button class="btn-approve" style="padding: 4px 10px; width:auto; display:inline-flex;" onclick="despacharPedido('${idVal}')">✅ Aprobar Pedido</button>` : ''}
                            ${(!esAnulado && !esDespachado) ? `<button class="btn-gold" style="padding: 4px 10px; width:auto; display:inline-flex; margin-left:4px;" onclick="editarPedido('${idVal}')">✏️ Editar</button>` : ''}
                            <button class="btn-gold" style="padding: 4px 10px; width:auto; display:inline-flex; margin-left:4px;" onclick="abrirModalPdf('/api/cotizaciones/${idVal}/pdf', 'Pedido N° ${numCot}', 'Pedido_${numCot}.pdf')">👁️ Ver</button>
                            ${!esAnulado ? `<button class="btn-danger" style="padding: 4px 8px; width:auto; display:inline-flex; margin-left:4px;" onclick="anularPedido('${idVal}')">🚫 Anular</button>` : '<span>-</span>'}
                        </td>
                    </tr>
                `;
            } catch (errRow) {
                console.error("Error renderizando fila de pedido:", errRow, c);
                return '';
            }
        });
    } catch (err) {
        console.error("Error cargando lista de pedidos:", err);
    }
}

async function despacharPedido(pedidoId) {
    if (!confirm('¿Deseas aprobar y despachar este pedido? Al hacerlo pasará al módulo de ventas.')) return;
    try {
        const res = await fetch(`/api/cotizaciones/${pedidoId}/despachar`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        
        if (res.ok) {
            const data = await res.json();
            if (data.estado_despacho === 'Pendiente') {
                alert('⚠️ Advertencia: No hay suficiente stock/materia prima. El pedido se despachó y pasó a Venta Parcial (Pendiente).');
            } else {
                alert('🚀 ¡Pedido aprobado con éxito y registrado como Venta!');
            }
            cargarMisCotizaciones();
        } else {
            const err = await res.json();
            alert(err.detail || 'Error al despachar el pedido.');
        }
    } catch (e) {
        console.error("Error al despachar pedido:", e);
        alert("Error de conexión al procesar el despacho.");
    }
}

function editarPedido(pedidoId) {
    const pedido = cotizacionesCache.find(c => String(c.id || c._id) === String(pedidoId));
    if (!pedido) return alert('No se encontró el pedido. Recarga la lista.');
    if ((pedido.estado || 'Pendiente') !== 'Pendiente') return alert('Solo se pueden editar pedidos pendientes.');

    if (carritoCotizacion.length > 0 && !pedidoEditandoId) {
        if (!confirm('Tienes productos en el carrito de pedido. Si continúas se reemplazarán por los del pedido a editar. ¿Continuar?')) return;
    }

    pedidoEditandoId = String(pedido.id || pedido._id);
    carritoCotizacion = (pedido.items || []).map(i => ({
        producto_id: i.producto_id,
        nombre: i.nombre,
        gramaje: Number(i.gramaje) || 0,
        cantidad: Number(i.cantidad) || 1,
        valor_add: 0,
        descuento: Number(i.descuento) || 0,
        presentacion: i.presentacion || 'Grano',
        gramos_totales: Number(i.gramos_totales) || 0,
        precio_unitario: Number(i.precio_unitario) || 0,
        subtotal: Number(i.subtotal) || 0
    }));

    document.getElementById('select-cliente-cot').value = pedido.cliente || '';
    document.getElementById('tipo-cot').value = pedido.tipo_venta || 'Normal';
    if (pedido.tipo_pago && pedido.tipo_pago !== 'N/A') document.getElementById('pago-cot').value = pedido.tipo_pago;
    const divPago = document.getElementById('div-metodo-pago-cot');
    if (divPago) divPago.style.display = (pedido.tipo_venta === 'Obsequio') ? 'none' : 'block';

    // OJO: no se llama toggleTipoVenta() aquí para no recalcular los precios que ya tenía el pedido
    renderCarrito('cotizacion');

    const num = pedido.consecutivo_str || String(pedidoEditandoId).substring(0, 8);
    document.getElementById('banner-edicion-num').innerText = 'Pedido N° ' + num;
    document.getElementById('banner-edicion-pedido').style.display = 'flex';
    document.getElementById('btn-procesar-cot').innerText = '💾 Guardar Cambios del Pedido';
    document.getElementById('card-carrito-pedido').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function cancelarEdicionPedido(silencioso = false) {
    if (!silencioso && carritoCotizacion.length > 0 && !confirm('¿Cancelar la edición? Se descartarán los cambios no guardados.')) return;
    pedidoEditandoId = null;
    carritoCotizacion = [];
    document.getElementById('select-cliente-cot').value = '';
    document.getElementById('tipo-cot').value = 'Normal';
    document.getElementById('pago-cot').value = 'Contado';
    const divPago = document.getElementById('div-metodo-pago-cot');
    if (divPago) divPago.style.display = 'block';
    document.getElementById('banner-edicion-pedido').style.display = 'none';
    document.getElementById('btn-procesar-cot').innerText = '📦 Registrar Pedido';
    renderCarrito('cotizacion');
}

async function anularPedido(pedidoId) {
    if (confirm('¿Deseas anular este pedido? Quedará registrado en el sistema como Anulado.')) {
        await fetch(`/api/cotizaciones/${pedidoId}/anular`, { method: 'PUT' });
        if (pedidoEditandoId === pedidoId) cancelarEdicionPedido(true);
        cargarMisCotizaciones();
    }
}
