// Gestión de usuarios del administrador (CU02, RF-01, RF-02).
// Los textos se ponen con textContent (nunca innerHTML) para que un nombre raro no pueda
// inyectar HTML en la página.

const $ = (id) => document.getElementById(id);

let usuarioActual = null;
let paginaActual = 1;
let totalPaginas = 1;
let temporizadorBusqueda = null;
let numeroSolicitud = 0;          // para ignorar respuestas viejas si el usuario sigue escribiendo
let alumnoEnEdicion = null;       // alumno al que se le capturan los datos académicos
let credencialesImportadas = [];  // contraseñas iniciales (solo viven en memoria)

function mostrarMensaje(elemento, texto, tipo) {
    elemento.textContent = texto;
    elemento.className = 'msg ' + (tipo || '');
}

function celda(texto) {
    const td = document.createElement('td');
    td.textContent = texto ?? '';
    return td;
}

// ------------------------------------------------------------ Registrar personal
function generarPassword() {
    const mayusculas = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
    const minusculas = 'abcdefghijkmnpqrstuvwxyz';
    const numeros = '23456789';
    const todos = mayusculas + minusculas + numeros;
    const azar = (n) => crypto.getRandomValues(new Uint32Array(1))[0] % n;
    const elegir = (cadena) => cadena[azar(cadena.length)];

    const caracteres = [elegir(mayusculas), elegir(numeros)];
    while (caracteres.length < 12) caracteres.push(elegir(todos));
    for (let i = caracteres.length - 1; i > 0; i--) {
        const j = azar(i + 1);
        [caracteres[i], caracteres[j]] = [caracteres[j], caracteres[i]];
    }
    return caracteres.join('');
}

async function agregarUsuario(evento) {
    evento.preventDefault();
    const mensaje = $('mensaje-form');
    mostrarMensaje(mensaje, '', '');

    const datos = {
        nombre: $('nombre').value.trim(),
        apellido_paterno: $('apellido-paterno').value.trim(),
        apellido_materno: $('apellido-materno').value.trim(),
        identificador: $('usuario-id').value.trim(),
        rol: $('rol').value,
        correo: $('correo').value.trim(),
        password: $('password').value
    };
    if (datos.rol === 'ALUMNO') {          // caso especial: alta manual de un alumno
        datos.curp = $('alumno-curp').value.trim().toUpperCase();
        datos.carrera = $('alumno-carrera').value.trim();
        datos.semestre = $('alumno-semestre').value;
        datos.telefono = $('alumno-telefono').value.trim();
        datos.domicilio = $('alumno-domicilio').value.trim();
        datos.password = datos.curp;       // el alumno entra con su CURP
    }
    const completo = [datos.nombre, datos.apellido_paterno, datos.apellido_materno]
        .filter(Boolean).join(' ');

    if (!confirm(`¿Registrar a ${completo} con el rol "${ETIQUETA_ROL[datos.rol]}"?`)) return;

    const boton = $('btn-guardar');
    boton.disabled = true;
    boton.textContent = 'Guardando…';
    try {
        const respuesta = await api('/api/admin/usuarios', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });
        const esAlumno = datos.rol === 'ALUMNO';
        mostrarMensaje(mensaje,
            `${respuesta.mensaje}. Usuario: ${datos.identificador} · Correo: ${respuesta.correo || datos.correo} · ` +
            (esAlumno
                ? `Contraseña inicial: su CURP (${respuesta.curp || datos.curp}).`
                : `Contraseña inicial: ${datos.password} ` +
                  '(entréguesela al usuario; deberá cambiarla en su primer ingreso).'),
            'ok');
        $('form-nuevo-usuario').reset();
        actualizarFormularioRol();
        paginaActual = 1;
        cargarUsuarios();
    } catch (e) {
        mostrarMensaje(mensaje, e.message, 'error');
    } finally {
        boton.disabled = false;
        boton.textContent = 'Guardar y Registrar Usuario';
    }
}

// El rol "Alumno" pide CURP, carrera y semestre, y arma el correo.
function actualizarFormularioRol() {
    const esAlumno = $('rol').value === 'ALUMNO';
    $('bloque-alumno').hidden = !esAlumno;
    $('bloque-alumno-2').hidden = !esAlumno;
    $('ayuda-correo').hidden = !esAlumno;
    $('label-usuario-id').textContent = esAlumno ? 'Número de control' : 'Número de empleado';
    $('usuario-id').placeholder = esAlumno ? 'Ej. 23170270' : 'Ej. EMP002';
    for (const id of ['alumno-curp', 'alumno-carrera', 'alumno-semestre']) {
        $(id).required = esAlumno;
    }
    $('correo').readOnly = esAlumno;
    // El alumno no captura contraseña: entra con su CURP.
    $('bloque-password').hidden = esAlumno;
    $('password').required = !esAlumno;
    if (esAlumno) $('password').value = '';
    if (esAlumno) {
        const control = $('usuario-id').value.trim();
        $('correo').value = /^\d{8}$/.test(control) ? `${control}@culiacan.tecnm.mx` : '';
    }
}

// ------------------------------------------------------------ Importar Excel
function descargarCredenciales() {
    const filas = [['Usuario (No. control)', 'Nombre', 'Correo', 'Contraseña inicial (CURP)']];
    for (const c of credencialesImportadas) filas.push([c.identificador, c.nombre, c.correo, c.password]);
    const csv = filas.map(f => f.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const enlace = document.createElement('a');
    enlace.href = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }));
    enlace.download = 'credenciales_alumnos.csv';
    enlace.click();
    URL.revokeObjectURL(enlace.href);
}

async function importarAlumnos(evento) {
    evento.preventDefault();
    const mensaje = $('mensaje-importar');
    const resultado = $('resultado-importar');
    mostrarMensaje(mensaje, '', '');
    resultado.replaceChildren();
    $('btn-descargar-cred').hidden = true;

    const datos = new FormData();
    datos.append('periodo', $('imp-periodo').value.trim());
    datos.append('fecha', $('imp-fecha').value);
    datos.append('archivo', $('imp-archivo').files[0]);

    const boton = $('btn-importar');
    boton.disabled = true;
    boton.textContent = 'Importando…';       // puede tardar con muchos alumnos
    try {
        const r = await api('/api/admin/alumnos/importar', { method: 'POST', body: datos });
        credencialesImportadas = r.credenciales;
        mostrarMensaje(mensaje,
            `Listo: ${r.creados} alumno(s) registrado(s), ${r.omitidos.length} fila(s) omitida(s). ` +
            (r.creados ? 'Descargue las credenciales ahora (la contraseña inicial de cada alumno es su CURP): no se volverán a mostrar.' : ''),
            r.creados ? 'ok' : 'error');
        if (r.creados) $('btn-descargar-cred').hidden = false;

        if (r.omitidos.length) {
            const lista = document.createElement('ul');
            lista.className = 'ayuda';
            for (const o of r.omitidos) {
                const li = document.createElement('li');
                li.textContent = `Fila ${o.fila} (${o.control}): ${o.motivo}`;
                lista.appendChild(li);
            }
            resultado.appendChild(lista);
        }
        $('imp-archivo').value = '';
        paginaActual = 1;
        cargarUsuarios();
    } catch (e) {
        mostrarMensaje(mensaje, e.message, 'error');
    } finally {
        boton.disabled = false;
        boton.textContent = 'Importar alumnos';
    }
}

// ------------------------------------------------------------ Datos académicos
function abrirAcademicos(usuario) {
    alumnoEnEdicion = usuario;
    $('acad-nombre').textContent = usuario.nombre_completo;
    $('form-academicos').reset();
    $('acad-plan').value = usuario.plan_estudios || '';
    $('acad-creditos').value = usuario.creditos ?? '';
    mostrarMensaje($('mensaje-acad'), '', '');
    actualizarBloqueAntiguo();
    $('panel-academicos').hidden = false;
    $('panel-academicos').scrollIntoView({ behavior: 'smooth' });
}

function actualizarBloqueAntiguo() {
    $('acad-antiguo').hidden = $('acad-plan').value !== 'ANTIGUO';
}

async function guardarAcademicos(evento) {
    evento.preventDefault();
    const mensaje = $('mensaje-acad');
    const datos = new FormData();
    datos.append('plan_estudios', $('acad-plan').value);
    datos.append('creditos', $('acad-creditos').value);
    if ($('acad-plan').value === 'ANTIGUO') {
        if ($('acad-foto').files[0]) datos.append('foto_infantil', $('acad-foto').files[0]);
        if ($('acad-boleta').files[0]) datos.append('boleta_extraescolares', $('acad-boleta').files[0]);
    }
    const boton = $('btn-guardar-acad');
    boton.disabled = true;
    try {
        const r = await api(`/api/admin/alumnos/${alumnoEnEdicion.id}/academicos`,
                            { method: 'POST', body: datos });
        mostrarMensaje(mensaje, r.mensaje, 'ok');
        cargarUsuarios();
        setTimeout(() => { $('panel-academicos').hidden = true; }, 1200);
    } catch (e) {
        mostrarMensaje(mensaje, e.message, 'error');
    } finally {
        boton.disabled = false;
    }
}

// ------------------------------------------------------------ Listado
function botonAccion(texto, clase, accion) {
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = clase;
    boton.textContent = texto;
    boton.addEventListener('click', accion);
    return boton;
}

function filaUsuario(u) {
    const fila = document.createElement('tr');

    const tdRol = document.createElement('td');
    const insignia = document.createElement('span');
    insignia.className = 'badge-rol ' + (CLASE_ROL[u.rol] || '');
    insignia.textContent = ETIQUETA_ROL[u.rol] || u.rol;
    tdRol.appendChild(insignia);

    const tdEstado = document.createElement('td');
    const estado = document.createElement('span');
    estado.className = 'badge-rol ' + (u.activo ? 'estado-activo' : 'estado-inactivo');
    estado.textContent = u.activo ? 'Activo' : 'Inactivo';
    tdEstado.appendChild(estado);
    const notas = [];
    if (u.debe_cambiar_password) notas.push('Aún no cambia su contraseña inicial');
    if (u.academicos_pendientes) notas.push('Faltan plan y créditos');
    for (const texto of notas) {
        const nota = document.createElement('small');
        nota.className = 'ayuda';
        nota.style.display = 'block';
        nota.textContent = texto;
        tdEstado.appendChild(nota);
    }

    const tdAcciones = document.createElement('td');
    if (u.rol === 'ALUMNO') {
        tdAcciones.appendChild(botonAccion(
            u.academicos_pendientes ? 'Capturar datos académicos' : 'Datos académicos',
            'btn-secundario', () => abrirAcademicos(u)));
    }
    if (u.id !== usuarioActual.id) {            // no puede tocar su propia cuenta
        tdAcciones.appendChild(botonAccion('Restablecer contraseña', 'btn-secundario',
            () => restablecerPassword(u)));
        tdAcciones.appendChild(botonAccion(u.activo ? 'Desactivar' : 'Activar',
            u.activo ? 'btn-eliminar' : 'btn-activar', () => cambiarEstado(u)));
    }

    fila.append(celda(u.nombre), celda(u.apellido_paterno), celda(u.apellido_materno),
                celda(u.identificador), celda(u.correo), tdRol, tdEstado, tdAcciones);
    return fila;
}

async function cargarUsuarios() {
    const solicitud = ++numeroSolicitud;
    const consulta = new URLSearchParams({
        q: $('filtro-q').value.trim(),
        rol: $('filtro-rol').value,
        pagina: paginaActual
    });
    const lista = $('mensaje-lista');
    mostrarMensaje(lista, '', '');
    try {
        const datos = await api('/api/admin/usuarios?' + consulta);
        if (solicitud !== numeroSolicitud) return;
        paginaActual = datos.pagina;
        totalPaginas = datos.paginas;

        const cuerpo = $('tabla-usuarios-body');
        cuerpo.replaceChildren();
        if (datos.usuarios.length === 0) {
            filaMensaje(cuerpo, 8, 'No se encontraron usuarios.');
        } else {
            for (const u of datos.usuarios) cuerpo.appendChild(filaUsuario(u));
        }
        $('info-pagina').textContent =
            `Página ${datos.pagina} de ${datos.paginas} · ${datos.total} usuario(s)`;
        $('btn-anterior').disabled = datos.pagina <= 1;
        $('btn-siguiente').disabled = datos.pagina >= datos.paginas;
    } catch (e) {
        mostrarMensaje(lista, e.message, 'error');
    }
}

async function cambiarEstado(usuario) {
    const activar = !usuario.activo;
    const texto = activar
        ? `¿Activar la cuenta de ${usuario.nombre_completo}?`
        : `¿Desactivar la cuenta de ${usuario.nombre_completo}? Ya no podrá iniciar sesión.`;
    if (!confirm(texto)) return;
    try {
        await api(`/api/admin/usuarios/${usuario.id}/estado`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ activo: activar })
        });
        cargarUsuarios();
    } catch (e) {
        mostrarMensaje($('mensaje-lista'), e.message, 'error');
    }
}

async function restablecerPassword(usuario) {
    const pregunta = usuario.rol === 'ALUMNO'
        ? `¿Restablecer la contraseña de ${usuario.nombre_completo} a su CURP? La actual dejará de funcionar.`
        : `¿Generar una contraseña temporal para ${usuario.nombre_completo}? La actual dejará de funcionar.`;
    if (!confirm(pregunta)) return;
    try {
        const r = await api(`/api/admin/usuarios/${usuario.id}/restablecer-password`, { method: 'POST' });
        mostrarMensaje($('mensaje-lista'),
            r.es_curp
                ? `La contraseña de ${r.identificador} se restableció a su CURP: ${r.password}`
                : `Contraseña temporal de ${r.identificador}: ${r.password} (entréguesela al usuario; deberá cambiarla al entrar).`,
            'ok');
        cargarUsuarios();
    } catch (e) {
        mostrarMensaje($('mensaje-lista'), e.message, 'error');
    }
}

function buscarConRetraso() {
    clearTimeout(temporizadorBusqueda);
    temporizadorBusqueda = setTimeout(() => { paginaActual = 1; cargarUsuarios(); }, 300);
}

// ------------------------------------------------------------ Inicio
document.addEventListener('DOMContentLoaded', async () => {
    usuarioActual = await requerirSesion('ADMINISTRADOR');
    if (!usuarioActual) return;
    $('admin-nombre').textContent = usuarioActual.nombre + ' · ';

    $('form-nuevo-usuario').addEventListener('submit', agregarUsuario);
    $('rol').addEventListener('change', actualizarFormularioRol);
    $('usuario-id').addEventListener('input', () => {
        if ($('rol').value === 'ALUMNO') actualizarFormularioRol();
    });
    $('btn-generar').addEventListener('click', () => { $('password').value = generarPassword(); });
    $('form-importar').addEventListener('submit', importarAlumnos);
    $('btn-descargar-cred').addEventListener('click', descargarCredenciales);
    $('form-academicos').addEventListener('submit', guardarAcademicos);
    $('acad-plan').addEventListener('change', actualizarBloqueAntiguo);
    $('btn-cancelar-acad').addEventListener('click', () => { $('panel-academicos').hidden = true; });
    $('filtro-q').addEventListener('input', buscarConRetraso);
    $('filtro-rol').addEventListener('change', buscarConRetraso);
    $('btn-anterior').addEventListener('click', () => { paginaActual--; cargarUsuarios(); });
    $('btn-siguiente').addEventListener('click', () => { paginaActual++; cargarUsuarios(); });

    actualizarFormularioRol();
    cargarUsuarios();
});
