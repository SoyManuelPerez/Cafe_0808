/* Usuarios (solo admin) */

async function cargarUsuarios() {
    try {
        const res = await fetch('/api/usuarios');
        const usuarios = await res.json();

        renderTablaPaginada('tabla-usuarios', usuarios, u => {
            const idVal = u.id || u._id || '';
            return `
                <tr>
                    <td><input type="text" id="usr-name-${idVal}" value="${u.username}" style="width: 150px;"></td>
                    <td>
                        <select id="usr-rol-${idVal}" style="width: 110px;">
                            <option value="ventas" ${u.rol === 'ventas' ? 'selected' : ''}>Ventas</option>
                            <option value="admin" ${u.rol === 'admin' ? 'selected' : ''}>Admin</option>
                        </select>
                    </td>
                    <td><input type="password" id="usr-pass-${idVal}" placeholder="Dejar en blanco para mantener" style="width: 180px;"></td>
                    <td>
                        <button class="btn-gold" style="padding: 4px 8px; width:auto;" onclick="guardarEdicionUsuario('${idVal}')">✏️ Guardar</button>
                        ${u.username !== 'admin' ? `<button class="btn-danger" style="padding: 4px 8px; width:auto;" onclick="eliminarUsuario('${idVal}')">❌ Eliminar</button>` : '<span style="color:#aaa; font-size:12px; margin-left:5px;">(Admin Principal)</span>'}
                    </td>
                </tr>
            `;
        });
    } catch (err) {
        console.error("Error cargando usuarios:", err);
    }
}

async function guardarUsuario(e) {
    e.preventDefault();
    const username = document.getElementById('usr-username').value;
    const password = document.getElementById('usr-password').value;
    const rol = document.getElementById('usr-rol').value;

    const res = await fetch('/api/usuarios', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ username, password, rol })
    });

    if (res.ok) {
        alert('Usuario creado con éxito');
        document.getElementById('form-usuario').reset();
        cargarUsuarios();
    } else {
        const err = await res.json();
        alert(err.detail || 'Error al crear usuario');
    }
}

async function guardarEdicionUsuario(id) {
    const nuevoUsername = document.getElementById(`usr-name-${id}`).value;
    const nuevaPassword = document.getElementById(`usr-pass-${id}`).value;
    const nuevoRol = document.getElementById(`usr-rol-${id}`).value;

    if (!nuevoUsername) return alert('El usuario no puede estar vacío');

    const res = await fetch('/api/usuarios/' + id, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ username: nuevoUsername, password: nuevaPassword || null, rol: nuevoRol })
    });

    if (res.ok) {
        alert('Usuario actualizado correctamente');
        cargarUsuarios();
    } else {
        const err = await res.json();
        alert(err.detail || 'Error al actualizar usuario');
    }
}

async function eliminarUsuario(id) {
    if (confirm('¿Está seguro de eliminar este usuario?')) {
        const res = await fetch('/api/usuarios/' + id, { method: 'DELETE' });
        if (res.ok) {
            alert('Usuario eliminado');
            cargarUsuarios();
        } else {
            const err = await res.json();
            alert(err.detail || 'Error al eliminar usuario');
        }
    }
}
