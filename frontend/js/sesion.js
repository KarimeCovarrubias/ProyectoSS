// Utilidades compartidas por TODAS las páginas internas. Cárgalo antes del JS de la página:
//   <script src="../../js/sesion.js"></script>      (desde html/admin/, html/alumno/, ...)
//
// La seguridad real la hace el servidor; esto solo manda al login si la sesión expiró.

const ETIQUETA_ROL = {
    ALUMNO: 'Alumno',
    JEFE_OFICINA_SS: 'Jefe(a) de Oficina de SS',
    JEFE_VINCULACION: 'Jefe(a) de Vinculación',
    ADMINISTRADOR: 'Administrador'
};

// Clases de color de los "badges" (ya existen en estilo_usuarios.css)
const CLASE_ROL = {
    ALUMNO: 'rol-alumno',
    JEFE_OFICINA_SS: 'rol-jefe',
    JEFE_VINCULACION: 'rol-vinculacion',
    ADMINISTRADOR: 'rol-admin'
};

const INICIO_POR_ROL = {
    ALUMNO: '/html/alumno/inicio.html',
    JEFE_OFICINA_SS: '/html/jefeSS/inicio.html',
    JEFE_VINCULACION: '/html/jefeVinc/inicio.html',
    ADMINISTRADOR: '/html/admin/inicio.html'
};

function irAInicio(rol) {
    window.location.href = INICIO_POR_ROL[rol] || '/html/login.html';
}

// Llama a la API y devuelve el JSON. Si algo falla lanza un Error con el mensaje
// del servidor (el mismo que se le muestra al usuario).
//   - 401: la sesión expiró -> manda al login
//   - CAMBIAR_PASSWORD: aún tiene la contraseña inicial -> manda a cambiarla
// Con FormData NO pongas Content-Type: el navegador lo agrega solo.
async function api(url, opciones = {}) {
    let respuesta;
    try {
        respuesta = await fetch(url, { credentials: 'same-origin', ...opciones });
    } catch (e) {
        throw new Error('No se pudo conectar con el servidor. Intente de nuevo.');
    }
    const datos = await respuesta.json().catch(() => ({}));

    if (respuesta.status === 401) {
        window.location.href = '/html/login.html';
        throw new Error('Su sesión expiró. Vuelva a iniciar sesión.');
    }
    if (!respuesta.ok) {
        if (datos.error?.codigo === 'CAMBIAR_PASSWORD') {
            window.location.href = '/html/cambiar_password.html';
        }
        const falla = new Error(datos.error?.mensaje || 'Ocurrió un error inesperado.');
        falla.estado = respuesta.status;
        throw falla;
    }
    return datos;
}

// Verifica que haya sesión (y el rol esperado). Devuelve el usuario:
//   { id, nombre, rol, debe_cambiar_password }   o null si ya redirigió.
//   requerirSesion('JEFE_OFICINA_SS').then(usuario => { ... });
async function requerirSesion(rolEsperado, permitirCambioPendiente = false) {
    let datos;
    try {
        datos = await api('/api/sesion');
    } catch (e) {
        window.location.href = '/html/login.html';
        return null;
    }
    if (datos.debe_cambiar_password && !permitirCambioPendiente) {
        window.location.href = '/html/cambiar_password.html';
        return null;
    }
    if (rolEsperado && datos.usuario.rol !== rolEsperado) {
        irAInicio(datos.usuario.rol);       // entró a una página que no es de su rol
        return null;
    }
    // Si el alumno ya liberó su servicio, se ocultan Carga / BP / PP y no se
    // permite entrar a esas páginas (el servidor también lo impide).
    if (datos.usuario.rol === 'ALUMNO' && !(await ajustarMenuAlumno())) return null;
    return { ...datos.usuario, debe_cambiar_password: datos.debe_cambiar_password };
}

// Quita del menú del alumno las opciones que dejan de tener sentido cuando su
// servicio social ya quedó LIBERADO. Devuelve false si hay que redirigirlo.
async function ajustarMenuAlumno() {
    try {
        const perfil = await api('/api/alumno/perfil');
        if (!perfil.servicio || perfil.servicio.estatus !== 'LIBERADO') return true;
        const paginas = new Set(['carga.html', 'bp.html', 'pp.html']);
        const actual = location.pathname.split('/').pop() || 'inicio.html';
        document.querySelectorAll('.menu .menu-item').forEach((enlace) => {
            const destino = (enlace.getAttribute('href') || '').split('/').pop();
            if (paginas.has(destino)) enlace.remove();
        });
        if (paginas.has(actual)) {
            window.location.replace('inicio.html');
            return false;
        }
        return true;
    } catch (e) {
        return true;        // si falla la consulta, no se bloquea la página
    }
}

async function cerrarSesion() {
    await fetch('/api/logout', { method: 'POST', credentials: 'same-origin' }).catch(() => {});
    window.location.href = '/html/login.html';
}

// Cualquier botón/enlace con id="btn-salir" cierra la sesión.
document.addEventListener('DOMContentLoaded', () => {
    const salir = document.getElementById('btn-salir');
    if (salir) {
        salir.addEventListener('click', (evento) => {
            evento.preventDefault();
            cerrarSesion();
        });
    }
    agregarMenuCambioPassword();
    marcarMenuActivo();
});

// Marca como activa SOLO la opción del menú que corresponde a la página actual,
// sin importar qué "active" haya quedado escrito a mano en el HTML.
function marcarMenuActivo() {
    const actual = location.pathname.split('/').pop() || 'inicio.html';
    document.querySelectorAll('.menu .menu-item').forEach((enlace) => {
        const destino = (enlace.getAttribute('href') || '').split('/').pop();
        enlace.classList.toggle('active', destino === actual);
    });
}

// Fechas: la BD guarda las horas en UTC ("2026-11-15 18:30:00") y las fechas sin hora
// ("2026-11-01"). Estas funciones las muestran en la hora y formato de México.
function fechaHora(fechaUtc) {
    if (!fechaUtc) return '';
    const fecha = new Date(fechaUtc.replace(' ', 'T') + 'Z');
    return fecha.toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
}

function fechaSolo(fechaIso) {
    if (!fechaIso) return '';
    return new Date(fechaIso + 'T00:00:00').toLocaleDateString('es-MX');
}

// ---- Ayudas para armar tablas SIN innerHTML (un dato raro no puede inyectar HTML) ----
function crearCelda(texto, clase) {
    const td = document.createElement('td');
    td.textContent = texto ?? '';
    if (clase) td.className = clase;
    return td;
}

function filaMensaje(cuerpo, columnas, texto) {
    cuerpo.replaceChildren();
    const tr = document.createElement('tr');
    const td = crearCelda(texto, 'texto-vacio');
    td.colSpan = columnas;
    td.style.textAlign = 'center';
    td.style.color = '#666';
    tr.appendChild(td);
    cuerpo.appendChild(tr);
}

// ---- Cambiar contraseña (todos los roles) ----
// Se agrega solo al final del sidebar (.menu) de cualquier página que cargue este archivo,
// así no hay que editar el HTML de cada rol. Abre una ventana emergente.
function validarPasswordNueva(p) {
    if (p.length < 10) return 'La nueva contraseña debe tener al menos 10 caracteres.';
    if (!/[A-Z]/.test(p)) return 'La nueva contraseña debe tener al menos una mayúscula.';
    if (!/\d/.test(p)) return 'La nueva contraseña debe tener al menos un número.';
    return null;
}

function agregarEstilosCambioPassword() {
    if (document.getElementById('estilos-cambio-pass')) return;
    const estilo = document.createElement('style');
    estilo.id = 'estilos-cambio-pass';
    estilo.textContent = `
        .modal-pass-fondo { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex;
            align-items: center; justify-content: center; z-index: 1000; padding: 20px; }
        .modal-pass { background: #fff; border-radius: 10px; padding: 28px; width: 100%; max-width: 420px;
            box-shadow: 0 8px 28px rgba(0,0,0,.25); font-family: Arial, sans-serif; }
        .modal-pass h2 { font-size: 20px; color: var(--tec-blue, #1b365d); margin-bottom: 8px; }
        .modal-pass p { font-size: 13px; color: #555; margin-bottom: 16px; }
        .modal-pass label { display: block; font-weight: bold; font-size: 14px; margin: 12px 0 6px; }
        .modal-pass input { width: 100%; padding: 10px; border: 1px solid #dcdcdc; border-radius: 4px; font-size: 15px; }
        .modal-pass .msg-pass { min-height: 20px; margin-top: 12px; font-size: 14px; }
        .modal-pass .msg-pass.error { color: #c5221f; }
        .modal-pass .msg-pass.ok { color: #137333; }
        .modal-pass .botones-pass { display: flex; gap: 10px; justify-content: flex-end; margin-top: 16px; }
        .modal-pass button { padding: 9px 18px; border-radius: 6px; font-weight: bold; font-size: 14px; cursor: pointer; }
        .modal-pass .btn-pass-guardar { background: var(--tec-blue, #1b365d); color: #fff; border: none; }
        .modal-pass .btn-pass-cancelar { background: #fff; color: var(--tec-blue, #1b365d);
            border: 1px solid var(--tec-blue, #1b365d); }
        .modal-pass button:disabled { opacity: .6; cursor: not-allowed; }`;
    document.head.appendChild(estilo);
}

function abrirCambioPassword() {
    if (document.getElementById('modal-pass-fondo')) return;
    agregarEstilosCambioPassword();

    const fondo = document.createElement('div');
    fondo.id = 'modal-pass-fondo';
    fondo.className = 'modal-pass-fondo';
    const caja = document.createElement('form');
    caja.className = 'modal-pass';

    const titulo = document.createElement('h2');
    titulo.textContent = 'Cambiar contraseña';
    const ayuda = document.createElement('p');
    ayuda.textContent = 'Mínimo 10 caracteres, al menos 1 mayúscula y 1 número.';
    caja.append(titulo, ayuda);

    const campos = {};
    [['actual', 'Contraseña actual'], ['nueva', 'Nueva contraseña'],
     ['confirmacion', 'Confirmar nueva contraseña']].forEach(([clave, texto]) => {
        const etiqueta = document.createElement('label');
        etiqueta.textContent = texto;
        const entrada = document.createElement('input');
        entrada.type = 'password';
        entrada.autocomplete = clave === 'actual' ? 'current-password' : 'new-password';
        etiqueta.htmlFor = entrada.id = 'pass-' + clave;
        campos[clave] = entrada;
        caja.append(etiqueta, entrada);
    });

    const mensaje = document.createElement('div');
    mensaje.className = 'msg-pass';
    const botones = document.createElement('div');
    botones.className = 'botones-pass';
    const cancelar = document.createElement('button');
    cancelar.type = 'button';
    cancelar.className = 'btn-pass-cancelar';
    cancelar.textContent = 'Cancelar';
    const guardar = document.createElement('button');
    guardar.type = 'submit';
    guardar.className = 'btn-pass-guardar';
    guardar.textContent = 'Guardar';
    botones.append(cancelar, guardar);
    caja.append(mensaje, botones);
    fondo.appendChild(caja);
    document.body.appendChild(fondo);
    campos.actual.focus();

    const cerrar = () => fondo.remove();
    const avisar = (texto, tipo) => { mensaje.textContent = texto; mensaje.className = 'msg-pass ' + tipo; };
    cancelar.addEventListener('click', cerrar);
    fondo.addEventListener('mousedown', (e) => { if (e.target === fondo) cerrar(); });

    caja.addEventListener('submit', async (e) => {
        e.preventDefault();
        const { actual, nueva, confirmacion } = Object.fromEntries(
            Object.entries(campos).map(([k, v]) => [k, v.value]));
        if (!actual || !nueva || !confirmacion) return avisar('Todos los campos son obligatorios.', 'error');
        if (nueva !== confirmacion) return avisar('La nueva contraseña y su confirmación no coinciden.', 'error');
        if (nueva === actual) return avisar('La nueva contraseña debe ser distinta de la actual.', 'error');
        const err = validarPasswordNueva(nueva);
        if (err) return avisar(err, 'error');

        guardar.disabled = true;
        guardar.textContent = 'Guardando…';
        try {
            const r = await api('/api/cambiar-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ actual, nueva, confirmacion })
            });
            avisar(r.mensaje || 'Contraseña actualizada correctamente.', 'ok');
            Object.values(campos).forEach((c) => { c.value = ''; c.disabled = true; });
            cancelar.textContent = 'Cerrar';
            guardar.style.display = 'none';
        } catch (falla) {
            avisar(falla.message, 'error');
            guardar.disabled = false;
            guardar.textContent = 'Guardar';
        }
    });
}

function agregarMenuCambioPassword() {
    const menu = document.querySelector('.menu');
    if (!menu || document.getElementById('menu-cambiar-pass')) return;
    const enlace = document.createElement('a');
    enlace.id = 'menu-cambiar-pass';
    enlace.href = '#';
    enlace.className = 'menu-item';
    enlace.textContent = 'Cambiar contraseña';
    enlace.addEventListener('click', (evento) => {
        evento.preventDefault();
        abrirCambioPassword();
    });
    menu.appendChild(enlace);
}