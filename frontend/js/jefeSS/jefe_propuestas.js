// Validación de propuestas propias de los alumnos.
document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('JEFE_OFICINA_SS');
    if (!usuario) return;
    document.getElementById('filtro-estatus').addEventListener('change', cargarPropuestas);
    cargarPropuestas();
});

function linea(etiqueta, valor) {
    const p = document.createElement('p');
    const e = document.createElement('strong');
    e.textContent = etiqueta + ': ';
    p.append(e, document.createTextNode(valor || '—'));
    return p;
}

async function cargarPropuestas() {
    const contenedor = document.getElementById('lista-propuestas');
    const estatus = document.getElementById('filtro-estatus').value;
    try {
        const lista = await api('/api/jefe/propuestas-propias?estatus=' + encodeURIComponent(estatus));
        contenedor.replaceChildren();
        if (lista.length === 0) {
            const vacio = document.createElement('p');
            vacio.className = 'texto-vacio';
            vacio.textContent = 'No hay propuestas propias en este estado.';
            contenedor.appendChild(vacio);
            return;
        }
        for (const p of lista) contenedor.appendChild(crearTarjeta(p));
    } catch (e) {
        aviso(document.getElementById('mensaje'), e.message, 'error');
    }
}

function crearTarjeta(p) {
    const tarjeta = document.createElement('article');
    tarjeta.className = 'propuesta-card';

    const encabezado = document.createElement('div');
    encabezado.className = 'propuesta-encabezado';
    const titulo = document.createElement('h3');
    titulo.textContent = p.nombre;
    encabezado.append(titulo, crearBadge(p.estatus));
    tarjeta.appendChild(encabezado);

    tarjeta.append(
        linea('Alumno', `${p.alumno_nombre} (${p.alumno_control}) · ${p.alumno_carrera}`),
        linea('Dependencia', p.empresa_nombre),
        linea('Responsable', p.titular),
        linea('Modalidad', p.origen === 'EXTERNA' ? 'Externa (fuera de la escuela)' : 'Interna'),
        linea('Periodo', p.periodo),
        linea('Horas', String(p.horas)),
        linea('Actividades', p.actividades));
    if (p.estatus === 'APROBADA') {
        tarjeta.append(linea('Lugares en el banco', `${p.cupo_disponible} de ${p.cupo}`),
                       linea('Validada', fechaLocal(p.validado_en)));
    }
    if (p.estatus === 'RECHAZADA') {
        tarjeta.append(linea('Motivo del rechazo', p.motivo_rechazo),
                       linea('Validada', fechaLocal(p.validado_en)));
    }
    if (p.estatus === 'PENDIENTE') {
        const acciones = document.createElement('div');
        acciones.className = 'acciones';
        acciones.append(crearBoton('Aprobar y agregar al banco', 'btn-guardar', () => aprobar(p)),
                        crearBoton('Rechazar', 'btn-peligro', () => rechazar(p)));
        tarjeta.appendChild(acciones);
    }
    return tarjeta;
}

async function validar(id, cuerpo) {
    const r = await api(`/api/jefe/propuestas-propias/${id}/validar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cuerpo)
    });
    aviso(document.getElementById('mensaje'), r.mensaje, 'ok');
    cargarPropuestas();
}

function aprobar(p) {
    const sinDefinir = (t) => (t && t !== 'Por definir' ? t : '');
    abrirModal({
        titulo: `Aprobar "${p.nombre}"`,
        descripcion: 'Completa los datos con los que se publicará en el banco. '
                     + 'El alumno que la propuso ya ocupa uno de los lugares.',
        textoBoton: 'Aprobar',
        campos: [
            { id: 'cupo', etiqueta: 'Lugares en total', tipo: 'number', valor: 1, min: 1, requerido: true },
            { id: 'plan_estudios', etiqueta: 'Válida para el plan', tipo: 'select', valor: 'AMBOS',
              opciones: [['AMBOS', 'Ambos planes'], ['NUEVO', 'Plan nuevo'], ['ANTIGUO', 'Plan antiguo']] },
            { id: 'horas', etiqueta: 'Horas', tipo: 'number', valor: p.horas, min: 1, requerido: true },
            { id: 'area_responsable', etiqueta: 'Área responsable', valor: p.area_responsable || '' },
            { id: 'objetivo', etiqueta: 'Objetivo', tipo: 'textarea', valor: p.objetivo || '' },
            { id: 'domicilio', etiqueta: 'Domicilio de la dependencia', valor: sinDefinir(p.domicilio) },
            { id: 'telefono', etiqueta: 'Teléfono de la dependencia', valor: sinDefinir(p.telefono) }
        ],
        alEnviar: (v) => validar(p.id, { aprobar: true, ...v })
    });
}

function rechazar(p) {
    abrirModal({
        titulo: `Rechazar "${p.nombre}"`,
        descripcion: 'El alumno verá este motivo y podrá elegir otro programa.',
        textoBoton: 'Rechazar',
        campos: [{ id: 'motivo', etiqueta: 'Motivo del rechazo', tipo: 'textarea', requerido: true }],
        alEnviar: (v) => validar(p.id, { aprobar: false, motivo: v.motivo })
    });
}
