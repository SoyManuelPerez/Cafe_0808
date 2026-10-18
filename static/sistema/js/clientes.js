/* Clientes */

async function cargarClientes() {
    try {
        const res = await fetch('/api/clientes');
        clientesCache = await res.json();

        renderTablaPaginada('tabla-clientes', clientesCache, c => {
            const idVal = c.id || c._id || '';
            return `
                <tr>
                    <td><input type="text" id="cli-nom-${idVal}" value="${c.nombre}" style="width: 180px;"></td>
                    <td><input type="text" id="cli-cel-${idVal}" value="${c.celular || ''}" style="width: 140px;"></td>
                    <td>
                        <button class="btn-gold" style="padding: 4px 8px; width:auto;" onclick="guardarEdicionCliente('${idVal}')">✏️ Guardar</button>
                        <button class="btn-danger" style="padding: 4px 8px; width:auto;" onclick="eliminarCliente('${idVal}')">❌ Eliminar</button>
                    </td>
                </tr>
            `;
        });
    } catch (err) {
        console.error("Error cargando clientes:", err);
    }
}

async function actualizarAutocompletarClientes(clienteSeleccionar = null) {
    try {
        const res = await fetch('/api/clientes');
        clientesCache = await res.json();

        const list = Array.isArray(clientesCache) ? clientesCache : [];
        const datalist = document.getElementById('lista-clientes-autocompletar');
        
        if (datalist) {
            datalist.innerHTML = '<option value="Cliente General">Cliente General</option>' +
                list.map(c => {
                    const celTxt = c.celular ? ` - 📱 ${c.celular}` : '';
                    return `<option value="${c.nombre}">${c.nombre}${celTxt}</option>`;
                }).join('');
        }

        if (clienteSeleccionar) {
            if (origenModalCliente === 'venta') {
                const inputVenta = document.getElementById('select-cliente-venta');
                if (inputVenta) inputVenta.value = clienteSeleccionar;
            } else if (origenModalCliente === 'cotizacion') {
                const inputCot = document.getElementById('select-cliente-cot');
                if (inputCot) inputCot.value = clienteSeleccionar;
            }
        }
    } catch (err) {
        console.error("Error actualizando autocompletado de clientes:", err);
    }
}

function abrirModalNuevoCliente(origen) {
    origenModalCliente = origen;
    document.getElementById('form-modal-cliente').reset();
    document.getElementById('modal-nuevo-cliente').style.display = 'flex';
    document.getElementById('modal-cli-nombre').focus();
}

function cerrarModalNuevoCliente() {
    document.getElementById('modal-nuevo-cliente').style.display = 'none';
}

async function guardarClienteModal(e) {
    e.preventDefault();
    const nombre = document.getElementById('modal-cli-nombre').value;
    const celular = document.getElementById('modal-cli-celular').value;

    try {
        const res = await fetch('/api/clientes', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nombre, celular })
        });

        if (res.ok) {
            cerrarModalNuevoCliente();
            await actualizarAutocompletarClientes(nombre);
            alert(`✅ Cliente "${nombre}" registrado y seleccionado con éxito.`);
        } else {
            const err = await res.json();
            alert(err.detail || 'Error al registrar el cliente');
        }
    } catch (err) {
        console.error("Error guardando cliente modal:", err);
        alert("Error de conexión al guardar cliente.");
    }
}

async function guardarCliente(e) {
    e.preventDefault();
    const nombre = document.getElementById('cli-nombre').value;
    const celular = document.getElementById('cli-celular').value;

    try {
        const res = await fetch('/api/clientes', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nombre, celular })
        });

        if (res.ok) {
            alert('✅ Cliente guardado con éxito');
            document.getElementById('form-cliente').reset();
            cargarClientes();
            actualizarAutocompletarClientes();
        } else {
            const err = await res.json();
            alert(err.detail || 'Error al guardar cliente');
        }
    } catch (err) {
        console.error("Error guardando cliente:", err);
        alert("Error de conexión al guardar cliente.");
    }
}

async function guardarEdicionCliente(id) {
    const nuevoNombre = document.getElementById(`cli-nom-${id}`).value;
    const nuevoCelular = document.getElementById(`cli-cel-${id}`).value;

    if (!nuevoNombre) return alert('El nombre no puede estar vacío');

    const res = await fetch('/api/clientes/' + id, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre: nuevoNombre, celular: nuevoCelular })
    });

    if (res.ok) {
        alert('Cliente actualizado con éxito');
        cargarClientes();
        actualizarAutocompletarClientes();
    }
}

async function eliminarCliente(id) {
    if (confirm('¿Eliminar cliente?')) {
        const res = await fetch('/api/clientes/' + id, { method: 'DELETE' });
        if (res.ok) {
            alert('Cliente eliminado');
            cargarClientes();
            actualizarAutocompletarClientes();
        }
    }
}
