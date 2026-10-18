/* Créditos (solo admin) */

async function cargarCreditos() {
    try {
        const res = await fetch('/api/ventas');
        const ventas = await res.json();
        const list = Array.isArray(ventas) ? ventas : [];
        
        const creditos = list.filter(v => v && v.tipo_pago === 'Crédito' && v.estado_credito === 'Pendiente' && v.tipo_venta !== 'Anulado');

        renderTablaPaginada('tabla-creditos', creditos, c => {
            const idVal = c.id || c._id || '';
            const numFact = c.consecutivo_str || (idVal ? String(idVal).substring(0,8) : 'N/A');
            return `<tr>
                <td>${numFact}</td>
                <td>${c.fecha || ''}</td>
                <td>${c.cliente || ''}</td>
                <td>${fmtCOP(c.total_venta)}</td>
                <td><span style="color: #ff6b6b; font-weight: bold;">${c.estado_credito || 'Pendiente'}</span></td>
                <td><button class="btn-approve" style="padding: 6px 12px; width:auto;" onclick="pagarCredito('${idVal}')">✅ Marcar Pagado</button></td>
            </tr>`;
        },
        {
            onFilter: (filteredList) => {
                let sum = filteredList.reduce((acc, c) => acc + (c.total_venta || 0), 0);
                document.getElementById('total-creditos-txt').innerText = fmtCOP(sum);

                let tfootCreditos = document.querySelector('#tabla-creditos tfoot');
                if (!tfootCreditos) {
                    tfootCreditos = document.createElement('tfoot');
                    document.querySelector('#tabla-creditos').appendChild(tfootCreditos);
                }
                tfootCreditos.innerHTML = `
                    <tr style="background-color: #1A1813; font-weight: bold; color: var(--gold-bright); border-top: 2px solid var(--gold-primary);">
                        <td colspan="3" style="text-align: right;">TOTAL PENDIENTE POR COBRAR:</td>
                        <td>${fmtCOP(sum)}</td>
                        <td colspan="2"></td>
                    </tr>
                `;
            }
        });
    } catch (err) {
        console.error("Error cargando créditos:", err);
    }
}

async function pagarCredito(id) {
    if (!confirm("¿Deseas marcar este crédito como PAGADO?")) return;
    try {
        const res = await fetch(`/api/ventas/${id}/pagar-credito`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' }
        });
        if (res.ok) {
            alert("Crédito pagado con éxito.");
            cargarCreditos();
        } else {
            const err = await res.json();
            alert("Error al actualizar: " + (err.error || err.detail || "Ocurrió un problema"));
        }
    } catch (err) {
        console.error("Error pagando crédito:", err);
        alert("Error de conexión al procesar el pago.");
    }
}
