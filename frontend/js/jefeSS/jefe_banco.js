// Banco de propuestas del Jefe de Oficina: alta de programas y consulta de lo que ve el alumno.
const ETIQUETA_PLAN = { NUEVO: 'Plan nuevo', ANTIGUO: 'Plan antiguo', AMBOS: 'Ambos planes' };

document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('JEFE_OFICINA_SS');
    if (!usuario) return;
    document.getElementById('form-programa').addEventListener('submit', crearPrograma);
    cargarProgramas();
});

async function cargarProgramas() {
    const cuerpo = document.getElementById('tabla-programas-body');
    try {
        const lista = await api('/api/jefe/programas');
        if (lista.length === 0) {
            filaMensaje(cuerpo, 8, 'Aún no hay propuestas en el banco.');
            return;
        }
        cuerpo.replaceChildren();
        for (const p of lista) {
            const tdPrograma = document.createElement('td');
            const nombre = document.createElement('strong');
            nombre.textContent = p.nombre;
            const detalle = document.createElement('small');
            detalle.textContent = p.actividades;
            tdPrograma.append(nombre, document.createElement('br'), detalle);

            const tdDependencia = document.createElement('td');
            const dep = document.createElement('span');
            dep.textContent = p.empresa_nombre;
            const resp = document.createElement('small');
            resp.textContent = `Responsable: ${p.titular}`;
            tdDependencia.append(dep, document.createElement('br'), resp);

            const esPropia = p.tipo === 'PROPIA';
            const tdAccion = document.createElement('td');
            if (!esPropia) {
                const activo = p.estatus === 'DISPONIBLE';
                tdAccion.appendChild(crearBoton(activo ? 'Ocultar' : 'Publicar', 'btn-secundario',
                    () => cambiarEstatus(p.id, activo ? 'INACTIVO' : 'DISPONIBLE')));
            }
            tdAccion.appendChild(crearBoton('Editar responsable', 'btn-secundario',
                () => editarResponsable(p)));
            const tdEstatus = document.createElement('td');
            tdEstatus.appendChild(crearBadge(p.estatus));

            const tr = document.createElement('tr');
            tr.append(tdPrograma, tdDependencia, crearCelda(p.periodo),
                      crearCelda(`${p.cupo_disponible} de ${p.cupo}`),
                      crearCelda(`${ETIQUETA_PLAN[p.plan_estudios] || p.plan_estudios} · `
                                 + (p.origen === 'EXTERNA' ? 'Externo' : 'Interno')),
                      crearCelda(esPropia ? `Propuesta propia de ${p.propuesto_por_nombre}` : 'Banco'),
                      tdEstatus, tdAccion);
            cuerpo.appendChild(tr);
        }
    } catch (e) {
        filaMensaje(cuerpo, 8, e.message);
    }
}

async function cambiarEstatus(id, estatus) {
    const mensaje = document.getElementById('mensaje');
    try {
        await api(`/api/jefe/programas/${id}/estatus`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estatus })
        });
        aviso(mensaje, estatus === 'DISPONIBLE' ? 'Propuesta publicada para los alumnos.'
                                                : 'Propuesta oculta: los alumnos ya no la ven.', 'ok');
        cargarProgramas();
    } catch (e) {
        aviso(mensaje, e.message, 'error');
    }
}

// Corrige la dependencia y el responsable de una sola propuesta.
function editarResponsable(p) {
    const mensaje = document.getElementById('mensaje');
    abrirModal({
        titulo: 'Dependencia y responsable',
        descripcion: `${p.nombre} · ${p.empresa_nombre}`,
        textoBoton: 'Guardar',
        campos: [
            { id: 'empresa', etiqueta: 'Dependencia / empresa', valor: p.empresa_nombre, requerido: true },
            { id: 'titular_nombre', etiqueta: 'Nombre(s) del responsable', valor: p.titular_nombre, requerido: true },
            { id: 'titular_apellido_paterno', etiqueta: 'Apellido paterno del responsable', valor: p.titular_apellido_paterno, requerido: true },
            { id: 'titular_apellido_materno', etiqueta: 'Apellido materno del responsable', valor: p.titular_apellido_materno, requerido: true },
            { id: 'domicilio', etiqueta: 'Domicilio de la dependencia', valor: p.domicilio, requerido: true },
            { id: 'telefono', etiqueta: 'Teléfono de la dependencia', valor: p.telefono, requerido: true }
        ],
        alEnviar: async (valores) => {
            if (!/^\d{10}$/.test(valores.telefono)) {
                throw new Error('El teléfono debe tener 10 dígitos.');
            }
            await api(`/api/jefe/programas/${p.id}/responsable`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(valores)
            });
            aviso(mensaje, 'Responsable actualizado correctamente.', 'ok');
            cargarProgramas();
        }
    });
}

async function crearPrograma(evento) {
    evento.preventDefault();
    const mensaje = document.getElementById('mensaje');
    const valor = (id) => document.getElementById(id).value.trim();
    const payload = {
        nombre: valor('p-nombre'), empresa: valor('p-empresa'),
        titular_nombre: valor('p-titular-nombre'),
        titular_apellido_paterno: valor('p-titular-paterno'),
        titular_apellido_materno: valor('p-titular-materno'),
        domicilio: valor('p-domicilio'), telefono: valor('p-telefono'),
        area_responsable: valor('p-area'), objetivo: valor('p-objetivo'),
        actividades: valor('p-actividades'), horas: valor('p-horas'), cupo: valor('p-cupo'),
        periodo: valor('p-periodo'), plan_estudios: valor('p-plan'), origen: valor('p-origen')
    };
    const boton = document.getElementById('btn-agregar');
    boton.disabled = true;
    try {
        const r = await api('/api/jefe/programas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        aviso(mensaje, r.mensaje, 'ok');
        document.getElementById('form-programa').reset();
        cargarProgramas();
    } catch (e) {
        aviso(mensaje, e.message, 'error');
    } finally {
        boton.disabled = false;
    }
}
