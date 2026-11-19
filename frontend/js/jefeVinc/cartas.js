// Cartas de terminación (Jefe de Vinculación).
// Lista los expedientes ya validados y permite subir / reemplazar el Word.
// Los textos se ponen con textContent (nunca innerHTML).

const $ = (id) => document.getElementById(id);
const MAX_BYTES = 5 * 1024 * 1024;       // 5 MB

let paginaActual = 1;
let temporizadorBusqueda = null;
let numeroSolicitud = 0;

function mostrarMensaje(texto, tipo) {
    const mensaje = $('mensaje-lista');
    mensaje.textContent = texto;
    mensaje.className = 'msg ' + (tipo || '');
}

function celda(texto) {
    const td = document.createElement('td');
    td.textContent = texto || '';
    return td;
}

// Validación en el navegador (el servidor la repite: RNF-07)
function validarWord(archivo) {
    if (!archivo.name.toLowerCase().endsWith('.docx')) {
        return 'Archivo no válido: solo se aceptan documentos Word (.docx)';
    }
    if (archivo.size > MAX_BYTES) {
        return 'Archivo no válido: el tamaño máximo es 5 MB';
    }
    return null;
}

async function subirCarta(servicio, archivo, boton) {
    const problema = validarWord(archivo);
    if (problema) {
        mostrarMensaje(problema, 'error');
        return;
    }
    const pregunta = servicio.documento_id
        ? `${servicio.nombre} ya tiene una carta. ¿Reemplazarla con "${archivo.name}"?\n` +
          'El alumno verá la nueva versión.'
        : `¿Subir la carta de terminación en Word (editable) de ${servicio.nombre}?\n` +
          `Archivo: ${archivo.name}\nEl alumno la descargará, la firmará y subirá el PDF.`;
    if (!confirm(pregunta)) return;

    const datos = new FormData();
    datos.append('archivo', archivo);
    const textoOriginal = boton.textContent;
    boton.disabled = true;
    boton.textContent = 'Subiendo…';          // indicador de progreso (RNF-04)
    mostrarMensaje('', '');
    try {
        const respuesta = await api(`/api/vinculacion/servicios/${servicio.servicio_id}/carta`,
                                    { method: 'POST', body: datos });
        mostrarMensaje(`${respuesta.mensaje} (${servicio.nombre}).`, 'ok');
        cargarServicios();
    } catch (e) {
        mostrarMensaje(e.message, 'error');
        boton.disabled = false;
        boton.textContent = textoOriginal;
    }
}

function filaServicio(s) {
    const fila = document.createElement('tr');

    const tdCarta = document.createElement('td');
    const insignia = document.createElement('span');
    insignia.className = 'badge-rol ' + (s.documento_id ? 'estado-activo' : 'estado-pendiente');
    insignia.textContent = s.documento_id ? 'Subida' : 'Pendiente';
    tdCarta.appendChild(insignia);
    if (s.documento_id) {
        const detalle = document.createElement('small');
        detalle.className = 'ayuda';
        detalle.textContent = ` v${s.version} · ${fechaHora(s.subido_en)}`;
        tdCarta.appendChild(detalle);
    }

    const tdAcciones = document.createElement('td');
    const contenedor = document.createElement('div');
    contenedor.className = 'acciones';

    const entrada = document.createElement('input');      // selector de archivo oculto
    entrada.type = 'file';
    entrada.accept = '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    entrada.hidden = true;

    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = s.documento_id ? 'btn-secundario' : 'btn-activar';
    boton.textContent = s.documento_id ? 'Reemplazar' : 'Subir carta';
    boton.addEventListener('click', () => entrada.click());
    entrada.addEventListener('change', () => {
        const archivo = entrada.files[0];
        if (archivo) subirCarta(s, archivo, boton);
        entrada.value = '';                               // permite elegir el mismo archivo otra vez
    });

    contenedor.append(boton, entrada);
    if (s.documento_id) {
        const ver = document.createElement('a');          // abre el PDF en otra pestaña
        ver.className = 'btn-secundario';
        ver.href = `/api/documentos/${s.documento_id}/archivo`;
        ver.target = '_blank';
        ver.rel = 'noopener';
        ver.textContent = 'Descargar';
        contenedor.appendChild(ver);
    }
    tdAcciones.appendChild(contenedor);

    fila.append(celda(s.nombre), celda(s.identificador), celda(s.carrera),
                celda(s.programa), celda(fechaSolo(s.fecha_fin)), tdCarta, tdAcciones);
    return fila;
}

async function cargarServicios() {
    const solicitud = ++numeroSolicitud;
    const consulta = new URLSearchParams({
        q: $('filtro-q').value.trim(),
        estado: $('filtro-estado').value,
        pagina: paginaActual
    });
    try {
        const datos = await api('/api/vinculacion/servicios?' + consulta);
        if (solicitud !== numeroSolicitud) return;        // llegó una respuesta más nueva
        paginaActual = datos.pagina;

        const cuerpo = $('tabla-cartas-body');
        cuerpo.replaceChildren();
        if (datos.servicios.length === 0) {
            const fila = document.createElement('tr');
            const td = celda('No hay alumnos con expediente validado que coincidan.');
            td.colSpan = 7;
            td.className = 'texto-vacio';
            fila.appendChild(td);
            cuerpo.appendChild(fila);
        } else {
            for (const s of datos.servicios) cuerpo.appendChild(filaServicio(s));
        }
        $('info-pagina').textContent =
            `Página ${datos.pagina} de ${datos.paginas} · ${datos.total} alumno(s)`;
        $('btn-anterior').disabled = datos.pagina <= 1;
        $('btn-siguiente').disabled = datos.pagina >= datos.paginas;
    } catch (e) {
        mostrarMensaje(e.message, 'error');
    }
}

function buscarConRetraso() {
    clearTimeout(temporizadorBusqueda);
    temporizadorBusqueda = setTimeout(() => {
        paginaActual = 1;
        cargarServicios();
    }, 300);
}

document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('JEFE_VINCULACION');
    if (!usuario) return;
    $('usuario-nombre').textContent = usuario.nombre + ' · ';

    $('filtro-q').addEventListener('input', buscarConRetraso);
    $('filtro-estado').addEventListener('change', buscarConRetraso);
    $('btn-anterior').addEventListener('click', () => { paginaActual--; cargarServicios(); });
    $('btn-siguiente').addEventListener('click', () => { paginaActual++; cargarServicios(); });
    cargarServicios();
});