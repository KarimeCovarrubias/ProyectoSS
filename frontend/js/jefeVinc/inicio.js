// No se actualiza solo a propósito: cada petición renueva la sesión y debe cerrarse
// tras 15 min de inactividad (RNF-02). Usa el botón "Actualizar datos".

function poner(id, valor) {
    document.getElementById(id).textContent = valor;
}

function celda(texto) {
    const td = document.createElement('td');
    td.textContent = texto || '';
    return td;
}

function llenarTabla(idCuerpo, filas, vacio) {
    const cuerpo = document.getElementById(idCuerpo);
    cuerpo.replaceChildren();
    if (filas.length === 0) {
        const tr = document.createElement('tr');
        const td = celda(vacio);
        td.colSpan = 3;
        td.className = 'texto-vacio';
        tr.appendChild(td);
        cuerpo.appendChild(tr);
        return;
    }
    for (const columnas of filas) {
        const tr = document.createElement('tr');
        tr.append(...columnas.map(celda));
        cuerpo.appendChild(tr);
    }
}

async function cargarResumen() {
    const alerta = document.getElementById('alerta-error');
    const boton = document.getElementById('btn-actualizar');
    alerta.hidden = true;
    boton.disabled = true;
    boton.textContent = 'Actualizando…';
    try {
        const datos = await api('/api/vinculacion/resumen');
        poner('stat-concluidos', datos.concluidos);
        poner('stat-pendientes', datos.cartas_pendientes);
        poner('stat-subidas', datos.cartas_subidas);
        llenarTabla('tabla-pendientes-body',
            datos.pendientes.map(p => [p.nombre, p.identificador, fechaSolo(p.fecha_fin)]),
            'No hay alumnos esperando su carta.');
        llenarTabla('tabla-recientes-body',
            datos.recientes.map(r => [r.nombre, r.identificador, fechaHora(r.subido_en)]),
            'Todavía no se ha subido ninguna carta.');
    } catch (e) {
        alerta.textContent = e.message;
        alerta.hidden = false;
    } finally {
        boton.disabled = false;
        boton.textContent = 'Actualizar datos';
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('JEFE_VINCULACION');
    if (!usuario) return;
    poner('usuario-nombre', usuario.nombre + ' · ');
    poner('nombre-bienvenida', usuario.nombre);
    document.getElementById('btn-actualizar').addEventListener('click', cargarResumen);
    cargarResumen();
});