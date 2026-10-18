/* Ventas: stock, histórico, edición, créditos del vendedor y ventas parciales */

async function cargarVentasData() {
    try {
        const resResumen = await fetch('/api/inventario/resumen');
        const dataResumen = await resResumen.json();
        
        const gridStock = document.getElementById('grid-detalles-stock');
        if (gridStock) {
            if (!dataResumen?.productos_stock || dataResumen.productos_stock.length === 0) {
                gridStock.innerHTML = '<div style="grid-column: 1/-1;">No hay productos en el catálogo</div>';
            } else {
                const productosFiltradosGrid = dataResumen.productos_stock.filter(p => {
                    const nom = String(p.nombre || '').toLowerCase();
                    const gram = parseFloat(p.gramaje) || 0;
                    return !nom.includes('2.5kg') && !nom.includes('2.5 kg') && gram !== 2500;
                });

                if (productosFiltradosGrid.length === 0) {
                    gridStock.innerHTML = '<div style="grid-column: 1/-1; color:#aaa;">No hay productos estándar disponibles</div>';
                } else {
                    gridStock.innerHTML = productosFiltradosGrid.map(p => `
                        <div class="stock-item">
                            <div class="stock-item-title">${p.nombre}</div>
                            <div class="stock-item-qty">${p.libras_disponibles} Lbs</div>
                        </div>
                    `).join('');
                }
            }
        }

        const resProds = await fetch('/api/productos');
        productosCache = await resProds.json();
        ordenarProductosArray(productosCache);
        
        const selectProd = document.getElementById('select-producto');
        if (selectProd) {
            selectProd.innerHTML = productosCache.map(p => {
                const pId = p.id || p._id;
                return `<option value="${pId}">${p.nombre} (${p.gramaje || 0}g) - ${fmtCOP(p.precio_venta)}</option>`;
            }).join('');
        }

        await actualizarAutocompletarClientes();
        cargarMisVentas();
    } catch (err) {
        console.error("Error al cargar ventas:", err);
    }
}

async function cargarMisVentas() {
    try {
        const res = await fetch('/api/ventas');
        if (!res.ok) throw new Error(`HTTP Error status: ${res.status}`);

        const ventas = await res.json();
        const list = Array.isArray(ventas) ? ventas : [];
        const misVentas = (rolActual === 'admin') ? list : list.filter(v => v && v.vendedor === usuarioActual);

        renderTablaPaginada('tabla-mis-ventas', misVentas, v => {
            try {
                if (!v) return '';
                const idVal = v.id || v._id || '';
                const numFact = v.consecutivo_str || (idVal ? String(idVal).substring(0,8) : 'N/A');
                
                const esAnulado = v.tipo_venta === 'Anulado' || v.estado_despacho === 'Anulado';
                const esPendiente = (v.estado_despacho || '') === 'Pendiente';

                let badgeEstado = '<span style="color:#2ecc71; font-weight:bold;">✅ Completa</span>';
                if (esAnulado) {
                    badgeEstado = '<span style="color:#ff6b6b; font-weight:bold;">🚫 Anulada</span>';
                } else if (esPendiente) {
                    badgeEstado = '<span style="color:#ff6b6b; font-weight:bold;">⏳ Pendiente</span>';
                }

                const estiloFila = esAnulado ? 'style="background-color: rgba(255, 107, 107, 0.15); color: #ff6b6b;"' : '';
                
                const esCredito = (v.tipo_pago || '') === 'Crédito';
                const creditoPendiente = (v.estado_credito || '') === 'Pendiente';
                const totalVenta = Number(v.total_venta || 0);

                return `
                    <tr ${estiloFila}>
                        <td><strong>${numFact}</strong></td>
                        <td>${v.fecha || 'N/A'}</td>
                        <td>${v.cliente || 'Cliente General'}</td>
                        <td>${v.tipo_venta || 'Normal'}</td>
                        <td>${badgeEstado}</td>
                        <td>
                            ${fmtCOP(totalVenta)} 
                            ${(esCredito && !esAnulado) ? `<br/><small style="color:${creditoPendiente ? '#ff6b6b' : '#2ecc71'};">💳 Crédito: ${v.estado_credito || 'Pendiente'}</small>` : ''}
                        </td>
                        <td>
                            <button class="btn-gold" style="padding: 4px 10px; width:auto; display:inline-flex;" onclick="abrirModalPdf('/api/ventas/${idVal}/pdf', 'Factura N° ${numFact}', 'Factura_${numFact}.pdf')">👁️ Ver Factura</button>
                            ${!esAnulado ? `
                                <button class="btn-gold" style="padding: 4px 10px; width:auto; display:inline-flex; margin-left:4px;" onclick="abrirModalEditarVenta('${idVal}', '${v.cliente || ''}', '${v.tipo_pago || ''}')">✏️ Editar</button>
                                ${(esCredito && creditoPendiente) ? `<button class="btn-approve" style="padding: 4px 10px; width:auto; display:inline-flex; margin-left:5px;" onclick="pagarCreditoVendedor('${idVal}')">✅ Pagado</button>` : ''}
                                <button class="btn-danger" style="padding: 4px 8px; width:auto; display:inline-flex; margin-left:4px;" onclick="anularVenta('${idVal}')">🚫 Anular</button>
                            ` : '<span>-</span>'}
                        </td>
                    </tr>
                `;
            } catch (errRow) {
                console.error("Error renderizando fila de mi venta:", errRow, v);
                return '';
            }
        });
    } catch (err) {
        console.error("Error cargando histórico de ventas:", err);
        const tbody = document.querySelector('#tabla-mis-ventas tbody');
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#ff6b6b;">Error al cargar ventas (${err.message})</td></tr>`;
    }
}

async function anularVenta(id) {
    if(confirm('¿Confirma que desea ANULAR esta venta? Quedará registrada como Anulada sin borrar datos.')) {
        await fetch(`/api/ventas/${id}/anular`, { method: 'PUT' });
        cargarMisVentas();
        if (document.getElementById('reportes').classList.contains('active')) {
            cargarReportes();
        }
        if (document.getElementById('gastos-sec').classList.contains('active')) {
            cargarModuloGastos();
        }
    }
}

async function abrirModalEditarVenta(ventaId, clienteActual, tipoPagoActual) {
    document.getElementById('edit-venta-id').value = ventaId;
    await actualizarAutocompletarClientes();
    
    const inputCliente = document.getElementById('edit-venta-cliente');
    if (inputCliente) {
        inputCliente.value = clienteActual || 'Cliente General';
    }
    
    const selectPago = document.getElementById('edit-venta-pago');
    if (selectPago) {
        selectPago.value = (tipoPagoActual === 'Efectivo') ? 'Contado' : (tipoPagoActual || 'Contado');
    }

    document.getElementById('modal-editar-venta').style.display = 'flex';
}

function cerrarModalEditarVenta() {
    document.getElementById('modal-editar-venta').style.display = 'none';
    document.getElementById('edit-venta-id').value = '';
}

async function guardarCambiosVenta() {
    const ventaId = document.getElementById('edit-venta-id').value;
    const nuevoCliente = document.getElementById('edit-venta-cliente').value.trim();
    const nuevoTipoPago = document.getElementById('edit-venta-pago').value;

    if (!nuevoCliente) {
        alert("Debe ingresar o seleccionar un cliente válido.");
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
            alert(data.mensaje || "Detalles de venta actualizados con éxito.");
            cerrarModalEditarVenta();
            cargarMisVentas();
            if (document.getElementById('reportes').classList.contains('active')) {
                cargarReportes();
            }
        } else {
            alert(data.detail || "Error al actualizar la venta.");
        }
    } catch (err) {
        console.error("Error al editar venta:", err);
        alert("Ocurrió un error de conexión.");
    }
}

async function pagarCreditoVendedor(id) {
    if(confirm('¿Marcar este crédito como pagado?')) {
        await fetch(`/api/ventas/${id}/pagar-credito`, { method: 'PUT' });
        cargarMisVentas();
    }
}

async function cargarVentasParciales() {
    try {
        const res = await fetch('/api/ventas');
        const ventas = await res.json();
        const list = Array.isArray(ventas) ? ventas : [];
        const parciales = list.filter(v => v && v.estado_despacho === 'Pendiente');

        renderTablaPaginada('tabla-parciales', parciales, v => {
            const idVal = v.id || v._id || '';
            const numFact = v.consecutivo_str || (idVal ? String(idVal).substring(0,8) : 'N/A');
            let faltantesStr = Object.keys(v.faltantes || {}).map(k => `${k}: ${v.faltantes[k]}`).join(', ');
            return `
                <tr>
                    <td><strong>${numFact}</strong></td>
                    <td>${v.fecha || ''}</td>
                    <td>${v.cliente || ''}</td>
                    <td>${v.vendedor || 'admin'}</td>
                    <td style="color:#ff6b6b; font-size:13px;">${faltantesStr}</td>
                    <td>${fmtCOP(v.total_venta)}</td>
                    <td>
                        <button class="btn-gold" style="padding: 4px 10px; width:auto;" onclick="completarDespacho('${idVal}')">✅ Despachar / Completar</button>
                        <button class="btn-danger" style="padding: 4px 8px; width:auto; margin-left:5px;" onclick="abrirModalPdf('/api/ventas/${idVal}/pdf', 'Factura N° ${numFact}', 'Factura_${numFact}.pdf')">👁️</button>
                    </td>
                </tr>
            `;
        });
    } catch (err) {
        console.error("Error cargando ventas parciales:", err);
    }
}

async function completarDespacho(id) {
    if(confirm('¿Deseas completar esta venta, descontar el stock faltante del inventario y pasarla a venta normal?')) {
        const res = await fetch(`/api/ventas/${id}/completar-despacho`, { method: 'PUT' });
        if(res.ok) {
            alert('¡Venta completada y stock descontado con éxito!');
            cargarVentasParciales();
        } else {
            const err = await res.json();
            alert(err.detail || 'Error al completar despacho. Asegúrate de tener suficiente inventario.');
        }
    }
}
