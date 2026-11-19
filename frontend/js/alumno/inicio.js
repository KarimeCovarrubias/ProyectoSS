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
            document.getElementById('alumno-estatus').className = 'badge-' +
                (d.servicio.estatus === 'LIBERADO' ? 'liberado'
                    : d.servicio.estatus === 'CONCLUIDO' ? 'concluido' : 'vigente');
            mostrarHoras(d.servicio);
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

// RF-08: las horas se acumulan por reporte bimestral validado (160 h por reporte).
function mostrarHoras(servicio) {
    document.getElementById('seccion-horas').style.display = 'block';
    document.getElementById('horas-acumuladas').textContent = servicio.horas_acumuladas;
    document.getElementById('horas-requeridas').textContent = servicio.horas_requeridas;
    document.getElementById('horas-porcentaje').textContent =
        `${servicio.porcentaje_avance}%`;
    document.getElementById('barra-horas').style.width =
        `${Math.min(100, servicio.porcentaje_avance)}%`;
    const detalle =
        `Reportes bimestrales validados: ${servicio.reportes_validados} de ` +
        `${servicio.reportes_requeridos}. Cada reporte validado suma ` +
        `${servicio.horas_por_reporte} horas.`;
    document.getElementById('horas-detalle').textContent =
        servicio.estatus === 'LIBERADO'
            ? 'Servicio social LIBERADO. ' + detalle
            : detalle;
}
