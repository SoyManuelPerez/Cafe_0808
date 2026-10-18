/* Empaques y etiquetas */

function calcularCostoEmpaqueUnitario() {
    const cant = parseInt(document.getElementById('emp-cantidad').value) || 0;
    const costo = parseFloat(document.getElementById('emp-costo').value) || 0;
    const u = cant > 0 ? (costo / cant) : 0;
    document.getElementById('costo-empaque-unitario-txt').innerText = fmtCOP(u);
}

async function guardarCompraEmpaque(e) {
    e.preventDefault();
    const payload = {
        tipo_empaque: document.getElementById('emp-tipo').value,
        fecha: document.getElementById('emp-fecha').value || new Date().toISOString().split('T')[0],
        cantidad: parseInt(document.getElementById('emp-cantidad').value),
        costo_total: parseFloat(document.getElementById('emp-costo').value)
    };

    const res = await fetch('/api/compras-empaques', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        alert('Compra de empaque guardada con éxito');
        document.getElementById('form-empaque').reset();
        document.getElementById('costo-empaque-unitario-txt').innerText = '$0';
        cargarModuloEmpaques();
    }
}

async function cargarModuloEmpaques() {
    try {
        const res = await fetch('/api/empaques/resumen');
        const data = await res.json();

        const nombresLegibles = {
            "bolsa_250g": "Bolsa 250g",
            "bolsa_500g": "Bolsa 500g",
            "etiqueta_250g": "Etiqueta 250g",
            "etiqueta_500g": "Etiqueta 500g"
        };

        const list = Object.keys(data || {}).map(k => ({ key: k, ...data[k] }));

        renderTablaPaginada('tabla-resumen-empaques', list, item => `
            <tr>
                <td><strong>${nombresLegibles[item.key] || item.key}</strong></td>
                <td>${(item.comprados || 0).toLocaleString('es-CO')} u.</td>
                <td>${(item.usados || 0).toLocaleString('es-CO')} u.</td>
                <td>
                    <input type="number" id="edit-disp-${item.key}" value="${item.disponibles || 0}" min="0" style="width: 100px;"> u.
                </td>
                <td>
                    <input type="number" id="edit-costo-${item.key}" value="${item.costo_unitario || 0}" min="0" step="any" style="width: 110px;">
                </td>
                <td>
                    <button class="btn-gold" style="padding: 4px 10px; width:auto;" onclick="guardarAjusteEmpaque('${item.key}')">💾 Guardar</button>
                </td>
            </tr>
        `);
    } catch (err) {
        console.error("Error cargando inventario empaques:", err);
    }
}

async function guardarAjusteEmpaque(tipoEmpaque) {
    const nuevosDisponibles = parseInt(document.getElementById(`edit-disp-${tipoEmpaque}`).value) || 0;
    const nuevoCostoUnitario = parseFloat(document.getElementById(`edit-costo-${tipoEmpaque}`).value) || 0;

    const res = await fetch('/api/empaques/ajuste-manual', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            tipo_empaque: tipoEmpaque,
            disponibles: nuevosDisponibles,
            costo_unitario: nuevoCostoUnitario
        })
    });

    if (res.ok) {
        alert('Empaque/Etiqueta actualizado con éxito');
        cargarModuloEmpaques();
    }
}
