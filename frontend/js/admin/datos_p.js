// Datos personales y de contacto (jefe de SS, jefe de Vinculación y administrador).
// MISMO archivo para los tres roles: no valida el rol aquí; lo valida el servidor
// (/api/personal/perfil responde 403 si el usuario no es personal). Así, una copia en
// la carpeta equivocada ya no te manda a Inicio.

document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion();          // solo exige que haya sesión
    if (!usuario) return;

    const mensaje = document.getElementById('mensaje-datos');
    const poner = (id, v) => {
        const el = document.getElementById(id);
        if (el) el.value = v ?? '';
    };

    try {
        const d = await api('/api/personal/perfil');
        poner('nombre', d.nombre);
        poner('apellido-paterno', d.apellido_paterno);
        poner('apellido-materno', d.apellido_materno);
        poner('correo', d.correo);
        poner('rol', ETIQUETA_ROL[d.rol] || d.rol);
        poner('telefono', d.telefono);
        poner('domicilio', d.domicilio);
    } catch (e) {
        console.error('Error al cargar los datos personales:', e);
        mensaje.textContent = e.message;
    }

    document.getElementById('form-datos').addEventListener('submit', actualizarDatos);
});

async function actualizarDatos(event) {
    event.preventDefault();
    const telefono = document.getElementById('telefono').value.trim();
    const domicilio = document.getElementById('domicilio').value.trim();

    if (telefono && !/^\d{10}$/.test(telefono)) {
        alert('El teléfono debe tener 10 dígitos.');
        return;
    }
    if (!confirm('¿Guardar los cambios?')) return;

    const boton = event.submitter || document.querySelector('.btn-guardar');
    boton.disabled = true;
    try {
        const r = await api('/api/personal/perfil', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ telefono, domicilio })
        });
        alert(r.mensaje || '¡Datos de contacto actualizados correctamente!');
    } catch (e) {
        alert('Error al actualizar: ' + e.message);
    } finally {
        boton.disabled = false;
    }
}