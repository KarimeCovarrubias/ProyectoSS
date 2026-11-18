document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('ALUMNO');
    if (!usuario) return;

    try {
        const d = await api('/api/alumno/perfil');
        const poner = (id, v) => { document.getElementById(id).value = v ?? ''; };
        // Datos académicos de solo lectura: si el HTML no los trae, se agregan debajo de la carrera
        const PLAN = { NUEVO: 'Plan nuevo', ANTIGUO: 'Plan antiguo' };
        const creditos = d.creditos === null ? 'Pendiente de captura'
            : `${d.creditos} (${d.porcentaje_creditos}%)`;
        agregarCampoLectura('semestre', 'Semestre', d.semestre, 'carrera');
        agregarCampoLectura('plan-estudios', 'Plan de servicio social',
                            PLAN[d.plan_estudios] || 'Pendiente de captura', 'semestre');
        agregarCampoLectura('creditos', 'Créditos acumulados', creditos, 'plan-estudios');

        poner('nombre', d.nombre);
        poner('apellido-paterno', d.apellido_paterno);
        poner('apellido-materno', d.apellido_materno);
        poner('control', d.identificador);
        poner('curp', d.curp);
        poner('carrera', d.carrera);
        poner('correo', d.correo);
        poner('telefono', d.telefono);
        poner('domicilio', d.domicilio);
    } catch (e) {
        document.getElementById('mensaje-datos').textContent = e.message;
    }
    document.getElementById('form-datos').addEventListener('submit', actualizarDatos);
});

function agregarCampoLectura(id, etiqueta, valor, despuesDe) {
    let entrada = document.getElementById(id);
    if (!entrada) {
        const ancla = document.getElementById(despuesDe)?.closest('.form-group');
        if (!ancla) return;
        const grupo = document.createElement('div');
        grupo.className = 'form-group';
        const label = document.createElement('label');
        label.htmlFor = id;
        label.textContent = etiqueta;
        entrada = document.createElement('input');
        entrada.id = id;
        entrada.type = 'text';
        grupo.append(label, entrada);
        ancla.after(grupo);
    }
    entrada.disabled = true;
    entrada.value = valor ?? '';
}

async function actualizarDatos(event) {
    event.preventDefault();
    const telefono = document.getElementById('telefono').value.trim();
    const domicilio = document.getElementById('domicilio').value.trim();

    if (telefono && !/^\d{10}$/.test(telefono)) {
        alert('El teléfono debe tener 10 dígitos.');
        return;
    }
    if (!confirm('¿Guardar los cambios?')) return;
    try {
        await api('/api/alumno/perfil', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ telefono, domicilio })
        });
        alert('¡Datos de contacto actualizados correctamente!');
    } catch (e) {
        alert('Error al actualizar: ' + e.message);
    }
}