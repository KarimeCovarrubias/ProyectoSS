// Revisión de los documentos PDF que suben los alumnos.
document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('JEFE_OFICINA_SS');
    if (!usuario) return;
    document.getElementById('filtro-estatus').addEventListener('change', cargarDocumentos);
    cargarDocumentos();
});

function nombreDocumento(d) {
    return d.tipo === 'REPORTE_BIMESTRAL' ? `Reporte bimestral #${d.numero_reporte}`
                                           : (NOMBRE_DOC[d.tipo] || d.tipo);
}

async function cargarDocumentos() {
    const cuerpo = document.getElementById('tabla-docs-body');
    const estatus = document.getElementById('filtro-estatus').value;
    try {
        const lista = await api('/api/jefe/documentos?estatus=' + encodeURIComponent(estatus));
        if (lista.length === 0) {
            filaMensaje(cuerpo, 7, 'No hay documentos en este estado.');
            return;
        }
        cuerpo.replaceChildren();
        for (const d of lista) {
            const tdAlumno = document.createElement('td');
            const nombre = document.createElement('strong');
            nombre.textContent = d.alumno_nombre;
            const detalle = document.createElement('small');
            detalle.textContent = `${d.alumno_control} · ${d.programa_nombre}`;
            tdAlumno.append(nombre, document.createElement('br'), detalle);

            const tdEstatus = document.createElement('td');
            tdEstatus.appendChild(crearBadge(d.estatus));

            const tdAcciones = document.createElement('td');
            tdAcciones.className = 'acciones';
            const ver = document.createElement('a');
            ver.href = `/api/jefe/documentos/${d.id}/archivo`;
            ver.target = '_blank';
            ver.rel = 'noopener';
            ver.className = 'btn-secundario';
            ver.textContent = 'Ver';
            tdAcciones.appendChild(ver);
            if (d.estatus === 'PENDIENTE') {
                tdAcciones.append(crearBoton('Validar', 'btn-guardar', () => validarDocumento(d)),
                                  crearBoton('Observar', 'btn-peligro', () => observarDocumento(d)));
            }

            const tr = document.createElement('tr');
            tr.append(tdAlumno, crearCelda(nombreDocumento(d)), crearCelda(`v${d.version}`),
                      crearCelda(fechaLocal(d.subido_en)), tdEstatus,
                      crearCelda(d.observacion || '—'), tdAcciones);
            cuerpo.appendChild(tr);
        }
    } catch (e) {
        filaMensaje(cuerpo, 7, e.message);
    }
}

async function revisar(id, cuerpo) {
    const r = await api(`/api/jefe/documentos/${id}/revisar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cuerpo)
    });
    aviso(document.getElementById('mensaje'), r.mensaje, 'ok');
    cargarDocumentos();
}

async function validarDocumento(d) {
    if (!confirm(`¿Validar "${nombreDocumento(d)}" de ${d.alumno_nombre}?`)) return;
    try {
        await revisar(d.id, { accion: 'VALIDAR' });
    } catch (e) {
        aviso(document.getElementById('mensaje'), e.message, 'error');
    }
}

function observarDocumento(d) {
    abrirModal({
        titulo: `Observar "${nombreDocumento(d)}"`,
        descripcion: `Los comentarios le aparecerán a ${d.alumno_nombre} para que corrija y suba otra versión.`,
        textoBoton: 'Enviar observaciones',
        campos: [{ id: 'texto', etiqueta: 'Observaciones', tipo: 'textarea', requerido: true }],
        alEnviar: (v) => revisar(d.id, { accion: 'OBSERVAR', texto: v.texto })
    });
}
