document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('ALUMNO');
    if (!usuario) return;

    try {
        const d = await api('/api/alumno/perfil');
        document.getElementById('alumno-nombre').textContent = d.nombre_completo;
        document.getElementById('alumno-control').textContent = d.identificador;
        document.getElementById('carrera-header').textContent = (d.carrera || 'PORTAL ALUMNO').toUpperCase();
        document.getElementById('alumno-semestre').textContent = d.semestre ?? '-';
        document.getElementById('alumno-creditos').textContent = d.creditos === null
            ? 'Pendiente de captura'
            : `${d.creditos} (${d.porcentaje_creditos}%)`;

        if (d.servicio) {
            document.getElementById('programa-titulo').textContent = d.servicio.programa_nombre;
            document.getElementById('programa-dep').textContent = d.servicio.empresa_nombre;
            document.getElementById('alumno-estatus').textContent = d.servicio.estatus;
        } else {
            document.getElementById('programa-titulo').textContent = 'Sin servicio activo';
            document.getElementById('programa-dep').textContent =
                d.bloqueo || 'Seleccione una propuesta en Carga o Propuesta Propia';
            document.getElementById('alumno-estatus').textContent = 'PENDIENTE';
        }
    } catch (e) {
        document.getElementById('programa-dep').textContent = e.message;
    }
});
