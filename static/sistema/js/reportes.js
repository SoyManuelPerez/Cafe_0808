/* Reportes generales */

async function cargarReportes() {
    try {
        const resVentas = await fetch('/api/ventas');
        if (!resVentas.ok) throw new Error(`HTTP Error status: ${resVentas.status}`);

        const ventas = await resVentas.json();
        const listVentas = Array.isArray(ventas) ? ventas : [];

        renderTablaPaginada('tabla-reportes', listVentas, v => {
            try {
                if (!v) return '';
                const tot = Number(v.total_venta || 0);
                const gan = Number(v.ganancia || 0);
                const fleteApp = Number(v.costo_envio_asociado || 0);
                const idVal = v.id || v._id || '';
                const numFact = v.consecutivo_str || (idVal ? String(idVal).substring(0,8) : 'N/A');
                const esAnulado = v.tipo_venta === 'Anulado' || v.estado_despacho === 'Anulado';

                let estadoTxt = '<span style="color:#2ecc71;">✅ Completa</span>';
                if (esAnulado) {
                    estadoTxt = '<span style="color:#ff6b6b; font-weight:bold;">🚫 Anulada</span>';
                } else if ((v.estado_despacho || '') === 'Pendiente') {
                    estadoTxt = '<span style="color:#ff6b6b;">⏳ Pendiente</span>';
                }

                const estiloFila = esAnulado ? 'style="background-color: rgba(255, 107, 107, 0.15); color: #ff6b6b;"' : '';

                return `
                    <tr ${estiloFila}>
                        <td><strong>${numFact}</strong></td>
                        <td>${v.fecha || 'N/A'}</td>
                        <td>${v.cliente || 'Cliente General'}</td>
                        <td>${v.vendedor || 'admin'}</td>
                        <td><strong>${v.tipo_venta || 'Normal'}</strong></td>
                        <td>${estadoTxt}</td>
                        <td>${fmtCOP(tot)}</td>
                        <td style="color: ${gan < 0 ? '#ff6b6b' : 'inherit'};">
                            ${fmtCOP(gan)}
                            ${fleteApp > 0 ? `<br/><small style="color:#aaa;">(Flete deducido: ${fmtCOP(fleteApp)})</small>` : ''}
                        </td>
                        <td><button class="btn-gold" style="padding: 4px 10px; width:auto;" onclick="abrirModalPdf('/api/ventas/${idVal}/pdf', 'Factura N° ${numFact}', 'Factura_${numFact}.pdf')">👁️ Ver Factura</button></td>
                        <td>${!esAnulado ? `<button class="btn-danger" style="padding: 4px 8px; width:auto;" onclick="anularVenta('${idVal}')">🚫 Anular</button>` : '<span>-</span>'}</td>
                    </tr>
                `;
            } catch (errRow) {
                console.error("Error renderizando fila en reporte de ventas:", errRow, v);
                return '';
            }
        }, {
            enableExcel: true,
            excelFileName: 'Historico_Ventas.xlsx',
            onFilter: (filteredVentas) => {
                let totalVentas = filteredVentas.reduce((acc, v) => acc + (v?.total_venta || 0), 0);
                let totalGanancia = filteredVentas.reduce((acc, v) => acc + (v?.ganancia || 0), 0);

                let tfootVentas = document.querySelector('#tabla-reportes tfoot');
                if (!tfootVentas) {
                    tfootVentas = document.createElement('tfoot');
                    document.querySelector('#tabla-reportes').appendChild(tfootVentas);
                }
                tfootVentas.innerHTML = `
                    <tr style="background-color: #1A1813; font-weight: bold; color: var(--gold-bright); border-top: 2px solid var(--gold-primary);">
                        <td colspan="6" style="text-align: right;">TOTALES FILTRADOS:</td>
                        <td>${fmtCOP(totalVentas)}</td>
                        <td style="color: ${totalGanancia < 0 ? '#ff6b6b' : 'var(--gold-bright)'};">${fmtCOP(totalGanancia)}</td>
                        <td colspan="2"></td>
                    </tr>
                `;
            }
        });
    } catch (err) {
        console.error("Error reporte ventas:", err);
        const tbody = document.querySelector('#tabla-reportes tbody');
        if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:#ff6b6b;">Error al cargar ventas (${err.message})</td></tr>`;
    }

    try {
        const resCompras = await fetch('/api/compras');
        const compras = await resCompras.json();

        renderTablaPaginada('tabla-reporte-compras', compras, c => `
            <tr>
                <td>${c.fecha || ''}</td>
                <td><strong>${c.producto_nombre || 'Materia Prima General'}</strong></td>
                <td>${(c.libras || 0).toLocaleString('es-CO')} Lbs</td>
                <td>${fmtCOP(c.costo_total)}</td>
                <td>${fmtCOP(c.costo_por_libra)}</td>
            </tr>
        `, {
            enableExcel: true,
            excelFileName: 'Reporte_Compras_Cafe.xlsx',
            onFilter: (filtered) => {
                let totalLbs = filtered.reduce((acc, c) => acc + (c.libras || 0), 0);
                let totalInv = filtered.reduce((acc, c) => acc + (c.costo_total || 0), 0);
                
                let tfootCompras = document.querySelector('#tabla-reporte-compras tfoot');
                if (!tfootCompras) {
                    tfootCompras = document.createElement('tfoot');
                    document.querySelector('#tabla-reporte-compras').appendChild(tfootCompras);
                }
                tfootCompras.innerHTML = `
                    <tr style="background-color: #1A1813; font-weight: bold; color: var(--gold-bright); border-top: 2px solid var(--gold-primary);">
                        <td colspan="2" style="text-align: right;">TOTALES:</td>
                        <td>${totalLbs.toFixed(1)} Lbs</td>
                        <td>${fmtCOP(totalInv)}</td>
                        <td>-</td>
                    </tr>
                `;
            }
        });
    } catch (err) {
        console.error("Error reporte compras:", err);
    }

    try {
        const resEmpaques = await fetch('/api/compras-empaques');
        const empaquesList = await resEmpaques.json();

        const nombresLegibles = {
            "bolsa_250g": "Bolsa 250g",
            "bolsa_500g": "Bolsa 500g",
            "etiqueta_250g": "Etiqueta 250g",
            "etiqueta_500g": "Etiqueta 500g"
        };

        renderTablaPaginada('tabla-reporte-empaques', empaquesList, e => `
            <tr>
                <td>${e.fecha || ''}</td>
                <td><strong>${nombresLegibles[e.tipo_empaque] || e.tipo_empaque}</strong></td>
                <td>${(e.cantidad || 0).toLocaleString('es-CO')} u.</td>
                <td>${fmtCOP(e.costo_total)}</td>
                <td>${fmtCOP(e.costo_unitario)}</td>
            </tr>
        `, {
            enableExcel: true,
            excelFileName: 'Reporte_Compras_Empaques.xlsx',
            onFilter: (filtered) => {
                let totalCant = filtered.reduce((acc, e) => acc + (e.cantidad || 0), 0);
                let totalInv = filtered.reduce((acc, e) => acc + (e.costo_total || 0), 0);

                let tfootEmp = document.querySelector('#tabla-reporte-empaques tfoot');
                if (!tfootEmp) {
                    tfootEmp = document.createElement('tfoot');
                    document.querySelector('#tabla-reporte-empaques').appendChild(tfootEmp);
                }
                tfootEmp.innerHTML = `
                    <tr style="background-color: #1A1813; font-weight: bold; color: var(--gold-bright); border-top: 2px solid var(--gold-primary);">
                        <td colspan="2" style="text-align: right;">TOTALES:</td>
                        <td>${totalCant.toLocaleString('es-CO')} u.</td>
                        <td>${fmtCOP(totalInv)}</td>
                        <td>-</td>
                    </tr>
                `;
            }
        });
    } catch (err) {
        console.error("Error reporte empaques:", err);
    }

    try {
        const resCot = await fetch('/api/cotizaciones');
        const cotizaciones = await resCot.json();

        renderTablaPaginada('tabla-reporte-cotizaciones', cotizaciones, c => {
            const tot = c.total_venta || 0;
            const idVal = c.id || c._id || '';
            const numCot = c.consecutivo_str || (idVal ? String(idVal).substring(0,8) : 'N/A');
            const estado = c.estado || 'Pendiente';
            const esAnulado = estado === 'Anulado';
            const esDespachado = estado === 'Despachado';

            let badgeEstado = '<span style="color:#2ecc71; font-weight:bold;">📦 Pendiente</span>';
            if (esAnulado) {
                badgeEstado = '<span style="color:#ff6b6b; font-weight:bold;">🚫 Anulado</span>';
            } else if (esDespachado) {
                badgeEstado = '<span style="color:#f5a70b; font-weight:bold;">✅ Despachado</span>';
            }

            const estiloFila = esAnulado ? 'style="background-color: rgba(255, 107, 107, 0.15); color: #ff6b6b;"' : '';

            return `
                <tr ${estiloFila}>
                    <td><strong>${numCot}</strong></td>
                    <td>${c.fecha || ''}</td>
                    <td>${c.cliente || ''}</td>
                    <td>${c.vendedor || 'admin'}</td>
                    <td>${badgeEstado}</td>
                    <td>${fmtCOP(tot)}</td>
                    <td><button class="btn-gold" style="padding: 4px 10px; width:auto;" onclick="abrirModalPdf('/api/cotizaciones/${idVal}/pdf', 'Pedido N° ${numCot}', 'Pedido_${numCot}.pdf')">👁️ Ver Pedido</button></td>
                    <td>${!esAnulado ? `<button class="btn-danger" style="padding: 4px 8px; width:auto;" onclick="anularPedido('${idVal}')">🚫 Anular</button>` : '<span>-</span>'}</td>
                </tr>
            `;
        }, {
            enableExcel: true,
            excelFileName: 'Historico_Pedidos.xlsx',
            onFilter: (filteredCot) => {
                let totalCot = filteredCot.reduce((acc, c) => acc + (c.total_venta || 0), 0);

                let tfootCot = document.querySelector('#tabla-reporte-cotizaciones tfoot');
                if (!tfootCot) {
                    tfootCot = document.createElement('tfoot');
                    document.querySelector('#tabla-reporte-cotizaciones').appendChild(tfootCot);
                }
                tfootCot.innerHTML = `
                    <tr style="background-color: #1A1813; font-weight: bold; color: var(--gold-bright); border-top: 2px solid var(--gold-primary);">
                        <td colspan="5" style="text-align: right;">TOTAL PEDIDOS:</td>
                        <td>${fmtCOP(totalCot)}</td>
                        <td colspan="2"></td>
                    </tr>
                `;
            }
        });
    } catch (err) {
        console.error("Error reporte pedidos:", err);
    }
}
