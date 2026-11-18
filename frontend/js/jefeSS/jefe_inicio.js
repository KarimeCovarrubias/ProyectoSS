// Inicio del Jefe de Oficina de SS: resumen real desde /api/jefe/resumen.
document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('JEFE_OFICINA_SS');
    if (!usuario) return;

    try {
        const datos = await api('/api/jefe/resumen');
        const poner = (id, valor) => {
            const nodo = document.getElementById(id);
            if (nodo) nodo.textContent = valor ?? 0;
        };
        poner('stat-pp', datos.propuestas_pendientes);
        poner('stat-docs', datos.documentos_pendientes);
        poner('stat-banco', datos.programas_banco);
    } catch (e) {
        const mensaje = document.createElement('div');
        mensaje.className = 'mensaje error';
        mensaje.textContent = e.message;
        const titulo = document.querySelector('.page-title');
        if (titulo) titulo.insertAdjacentElement('afterend', mensaje);
    }
});
