document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('ALUMNO');
    if (!usuario) return;

    document.getElementById('form-propuesta').addEventListener('submit', enviarPropuesta);
    cargarPropuestas();
});

function avisoPP(texto, tipo) {
    const caja = document.getElementById('mensaje-pp');
    if (!caja) return;
    caja.textContent = texto || '';
    caja.className = 'mensaje-pp' + (texto && tipo ? ' ' + tipo : '');
}

async function enviarPropuesta(event) {
    event.preventDefault();
    const valor = (id) => document.getElementById(id).value.trim();
    const telefono = valor('telefono');
    if (!/^[0-9]{10}$/.test(telefono)) {
        avisoPP('El teléfono debe tener exactamente 10 dígitos.', 'error');
        return;
    }

    const payload = {
        nombre: valor('nombre'),
        dependencia: valor('dependencia'),
        responsable_nombre: valor('responsable_nombre'),
        responsable_apellido_paterno: valor('responsable_apellido_paterno'),
        responsable_apellido_materno: valor('responsable_apellido_materno'),
        domicilio: valor('domicilio'),
        telefono,
        origen: document.getElementById('subtipo').value,
        periodo: valor('periodo'),
        actividades: valor('actividades')
    };

    const boton = event.target.querySelector('button[type="submit"]');
    boton.disabled = true;
    boton.textContent = 'Enviando…';
    try {
        const r = await api('/api/alumno/propuesta-propia', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        avisoPP(r.mensaje || 'Propuesta enviada para revisión.', 'ok');
        event.target.reset();
        cargarPropuestas();
    } catch (e) {
        avisoPP(e.message, 'error');
    } finally {
        boton.disabled = false;
        boton.textContent = 'Enviar Propuesta para Revisión';
    }
}

async function cargarPropuestas() {
    const cuerpo = document.getElementById('tabla-pp-body');
    if (!cuerpo) return;
    try {
        const lista = await api('/api/alumno/mis-propuestas');
        if (!lista.length) {
            filaMensaje(cuerpo, 6, 'Todavía no ha registrado propuestas propias.');
            return;
        }
        cuerpo.replaceChildren();
        for (const p of lista) {
            const responsable = p.titular
                || [p.titular_nombre, p.titular_apellido_paterno, p.titular_apellido_materno]
                    .filter(Boolean).join(' ');

            const tdEstatus = document.createElement('td');
            const badge = document.createElement('span');
            badge.className = 'badge-pp ' + (p.estatus || 'PENDIENTE').toLowerCase();
            badge.textContent = p.estatus || 'PENDIENTE';
            tdEstatus.appendChild(badge);

            const motivo = p.estatus === 'RECHAZADA'
                ? (p.motivo_rechazo || 'Sin motivo registrado')
                : p.estatus === 'PENDIENTE' ? 'Pendiente de revisión' : '—';

            const tr = document.createElement('tr');
            tr.append(crearCelda(p.nombre), crearCelda(p.dependencia),
                      crearCelda(responsable), crearCelda(p.periodo), tdEstatus,
                      crearCelda(motivo));
            cuerpo.appendChild(tr);
        }
    } catch (e) {
        filaMensaje(cuerpo, 6, e.message);
    }
}
