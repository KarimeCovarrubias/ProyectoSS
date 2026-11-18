// Inicio del administrador. Datos reales desde /api/admin/resumen.
// OJO: no se actualiza solo cada cierto tiempo a propósito: cada petición renueva la
// sesión y el sistema debe cerrarla tras 15 min de inactividad (RNF-02).

const ACCION_LEGIBLE = {
    LOGIN: 'Inició sesión',
    LOGOUT: 'Cerró sesión',
    LOGIN_FALLIDO: 'Intento de acceso fallido',
    CUENTA_BLOQUEADA: 'Cuenta bloqueada',
    ALTA_USUARIO: 'Alta de usuario',
    ACTIVAR_USUARIO: 'Cuenta activada',
    DESACTIVAR_USUARIO: 'Cuenta desactivada',
    CAMBIO_PASSWORD: 'Cambió su contraseña'
};

function poner(id, valor) {
    document.getElementById(id).textContent = valor;
}

// La BD guarda las fechas en UTC ("2026-11-15 18:30:00"): se muestran en hora local.
function fechaLocal(fechaUtc) {
    const fecha = new Date(fechaUtc.replace(' ', 'T') + 'Z');
    return fecha.toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
}

function celda(texto) {
    const td = document.createElement('td');
    td.textContent = texto || '';
    return td;
}

function mostrarRoles(porRol) {
    const contenedor = document.getElementById('roles-resumen');
    contenedor.replaceChildren();
    for (const [rol, cantidad] of Object.entries(porRol)) {
        const item = document.createElement('div');
        item.className = 'rol-item';
        const etiqueta = document.createElement('span');
        etiqueta.textContent = ETIQUETA_ROL[rol] || rol;
        const numero = document.createElement('strong');
        numero.textContent = cantidad;
        item.append(etiqueta, numero);
        contenedor.appendChild(item);
    }
}

function mostrarActividad(registros) {
    const cuerpo = document.getElementById('tabla-actividad-body');
    cuerpo.replaceChildren();
    if (registros.length === 0) {
        const fila = document.createElement('tr');
        const td = celda('Todavía no hay actividad registrada.');
        td.colSpan = 4;
        td.className = 'texto-vacio';
        fila.appendChild(td);
        cuerpo.appendChild(fila);
        return;
    }
    for (const r of registros) {
        const fila = document.createElement('tr');
        fila.append(
            celda(fechaLocal(r.fecha)),
            celda(r.usuario),
            celda(ACCION_LEGIBLE[r.accion] || r.accion),
            celda(r.detalle)
        );
        cuerpo.appendChild(fila);
    }
}

async function cargarResumen() {
    const alerta = document.getElementById('alerta-error');
    const boton = document.getElementById('btn-actualizar');
    alerta.hidden = true;
    boton.disabled = true;
    boton.textContent = 'Actualizando…';
    try {
        const datos = await api('/api/admin/resumen');
        poner('stat-usuarios', datos.usuarios);
        poner('stat-banco', datos.programas_banco);
        poner('stat-expedientes', datos.expedientes_activos);
        mostrarRoles(datos.por_rol);
        mostrarActividad(datos.actividad_reciente);
    } catch (e) {
        alerta.textContent = e.message;
        alerta.hidden = false;
    } finally {
        boton.disabled = false;
        boton.textContent = 'Actualizar datos';
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('ADMINISTRADOR');
    if (!usuario) return;
    poner('admin-nombre', usuario.nombre + ' · ');
    poner('nombre-bienvenida', usuario.nombre);
    document.getElementById('btn-actualizar').addEventListener('click', cargarResumen);
    cargarResumen();
});