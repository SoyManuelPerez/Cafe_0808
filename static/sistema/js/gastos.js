/* Otros gastos y comparativa financiera */

async function cargarModuloGastos() {
    try {
        const resGastos = await fetch('/api/gastos');
        const gastos = await resGastos.json();
        otrosGastosCache = Array.isArray(gastos) ? gastos : [];

        const resVentas = await fetch('/api/ventas');
        const ventas = await resVentas.json();
        const listVentas = Array.isArray(ventas) ? ventas : [];

        const totalGananciasBrutas = listVentas
            .filter(v => v && v.tipo_venta !== 'Anulado' && v.estado_despacho !== 'Anulado')
            .reduce((sum, v) => sum + (v.ganancia || 0), 0);

        const totalOtrosGastos = otrosGastosCache.reduce((sum, g) => sum + (g.monto || 0), 0);

        const gananciaNetaReal = totalGananciasBrutas - totalOtrosGastos;

        document.getElementById('kpi-ganancias-brutas').innerText = fmtCOP(totalGananciasBrutas);
        document.getElementById('kpi-otros-gastos').innerText = fmtCOP(totalOtrosGastos);

        const elNeta = document.getElementById('kpi-ganancia-neta');
        elNeta.innerText = fmtCOP(gananciaNetaReal);
        elNeta.style.color = gananciaNetaReal < 0 ? '#ff6b6b' : 'var(--gold-bright)';

        renderTablaPaginada('tabla-gastos', otrosGastosCache, g => {
            const idVal = g.id || g._id || '';
            return `
                <tr>
                    <td>${g.fecha || 'N/A'}</td>
                    <td><strong style="color:#ff6b6b;">${fmtCOP(g.monto)}</strong></td>
                    <td>${g.observacion || '-'}</td>
                    <td>
                        <button class="btn-danger" style="padding: 4px 8px; width:auto;" onclick="eliminarGasto('${idVal}')">🚫 Eliminar</button>
                    </td>
                </tr>
            `;
        }, {
            enableExcel: true,
            excelFileName: 'Historico_Otros_Gastos.xlsx'
        });

        const campoFechaGasto = document.getElementById('gasto-fecha');
        if (campoFechaGasto && !campoFechaGasto.value) {
            campoFechaGasto.value = new Date().toISOString().split('T')[0];
        }
    } catch (err) {
        console.error("Error al cargar módulo de gastos:", err);
    }
}

async function guardarGasto(e) {
    e.preventDefault();
    const monto = parseFloat(document.getElementById('gasto-monto').value);
    const fecha = document.getElementById('gasto-fecha').value;
    const observacion = document.getElementById('gasto-observacion').value.trim();

    if (isNaN(monto) || monto <= 0) {
        alert("Ingrese un monto válido para el gasto.");
        return;
    }

    try {
        const res = await fetch('/api/gastos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                monto: monto,
                fecha: fecha,
                observacion: observacion
            })
        });

        if (res.ok) {
            alert("💸 Gasto registrado con éxito.");
            document.getElementById('form-gasto').reset();
            cargarModuloGastos();
        } else {
            const err = await res.json();
            alert(err.detail || "Error al registrar el gasto.");
        }
    } catch (err) {
        console.error("Error guardando gasto:", err);
        alert("Error de conexión al registrar el gasto.");
    }
}

async function eliminarGasto(id) {
    if (confirm("¿Confirma que desea eliminar este registro de gasto?")) {
        try {
            const res = await fetch(`/api/gastos/${id}`, { method: 'DELETE' });
            if (res.ok) {
                alert("Gasto eliminado.");
                cargarModuloGastos();
            } else {
                alert("Error al eliminar el gasto.");
            }
        } catch (err) {
            console.error("Error eliminando gasto:", err);
        }
    }
}
