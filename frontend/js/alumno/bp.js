document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('ALUMNO');
    if (!usuario) return;

    const cuerpo = document.getElementById('tabla-bp-body');
    try {
        const programas = await api('/api/programas/banco');
        if (programas.length === 0) {
            filaMensaje(cuerpo, 6, 'No hay propuestas registradas en el banco.');
            return;
        }
        cuerpo.replaceChildren();
        for (const p of programas) {
            const tr = document.createElement('tr');
            // Las propuestas propias aprobadas de otros alumnos son solo de consulta (ya tienen dueño)
            const lugares = p.tipo === 'PROPIA'
                ? `Propuesta propia (${p.origen === 'EXTERNA' ? 'externa' : 'interna'})`
                : `${p.cupo_disponible} de ${p.cupo} lugares`;
            const responsable = p.titular
                || [p.titular_nombre, p.titular_apellido_paterno, p.titular_apellido_materno]
                    .filter(Boolean).join(' ');
            tr.append(crearCelda(p.nombre), crearCelda(p.empresa_nombre),
                      crearCelda(responsable), crearCelda(p.actividades),
                      crearCelda(p.periodo), crearCelda(lugares));
            cuerpo.appendChild(tr);
        }
    } catch (e) {
        filaMensaje(cuerpo, 6, e.message);
    }
});