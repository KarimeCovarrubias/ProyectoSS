document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('ALUMNO');
    if (!usuario) return;
    cargarEstadoCarga();
});

async function cargarEstadoCarga() {
    const mensaje = document.getElementById('mensaje-estado');
    const cuerpo = document.getElementById('tabla-body');
    try {
        const datos = await api('/api/alumno/perfil');
        if (datos.servicio) {
            document.getElementById('seccion-cargada').style.display = 'block';
            document.getElementById('cargada-nombre').textContent = datos.servicio.programa_nombre;
            document.getElementById('cargada-dep').textContent =
                `Dependencia: ${datos.servicio.empresa_nombre} | Horas: ${datos.servicio.horas_requeridas}`;
            document.getElementById('cargada-estatus').textContent = datos.servicio.estatus;
            document.getElementById('seccion-disponibles').style.display = 'none';
            mensaje.textContent = 'Ya cuenta con un servicio social registrado.';
            return;
        }
        if (datos.bloqueo) {                       // curso de inducción, plan/créditos pendientes...
            mensaje.textContent = datos.bloqueo;
            filaMensaje(cuerpo, 5, 'Aún no puede seleccionar un programa.');
            return;
        }

        const programas = await api('/api/alumno/programas-disponibles');
        if (programas.length === 0) {
            filaMensaje(cuerpo, 5, 'No hay programas disponibles para su plan en este momento.');
            return;
        }
        cuerpo.replaceChildren();
        for (const p of programas) {
            const tr = document.createElement('tr');

            const tdPrograma = document.createElement('td');
            const nombre = document.createElement('strong');
            nombre.textContent = p.nombre;
            const actividades = document.createElement('small');
            actividades.textContent = p.actividades;
            tdPrograma.append(nombre, document.createElement('br'), actividades);

            const boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'btn-cargar';
            boton.textContent = 'Seleccionar';
            boton.addEventListener('click', () => seleccionarPrograma(p.id, p.nombre));
            const tdAccion = document.createElement('td');
            tdAccion.appendChild(boton);

            tr.append(tdPrograma, crearCelda(p.empresa_nombre), crearCelda(p.periodo),
                      crearCelda(`${p.cupo_disponible} / ${p.cupo}`), tdAccion);
            cuerpo.appendChild(tr);
        }
    } catch (e) {
        mensaje.textContent = 'Error al cargar los datos: ' + e.message;
    }
}

async function seleccionarPrograma(programaId, nombre) {
    if (!confirm(`¿Seleccionar el programa "${nombre}"? Esta acción registrará su solicitud de servicio social.`)) return;
    try {
        await api('/api/alumno/seleccionar-programa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ programa_id: programaId })
        });
        alert('¡Programa seleccionado correctamente!');
        location.reload();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}
