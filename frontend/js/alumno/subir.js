document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('ALUMNO');
    if (!usuario) return;
    cargarDocumentos();
});

const NOMBRE_DOCUMENTO = {
    CARTA_PRESENTACION: 'Carta de presentación',
    SOLICITUD: 'Solicitud de servicio social',
    CARTA_ACEPTACION: 'Carta de aceptación',
    MEMORIA_FINAL: 'Memoria final',
    CARTA_TERMINACION: 'Carta de terminación'
};
const CLASE_ESTATUS = {
    PENDIENTE: 'badge-pendiente', VALIDADO: 'badge-validado',
    OBSERVADO: 'badge-observado', SIN_SUBIR: 'badge-sin-subir',
    DISPONIBLE: 'badge-validado'
};

function fechaCorta(iso) {
    if (!iso) return '';
    const [a, m, d] = iso.split('-').map(Number);
    return new Date(a, m - 1, d).toLocaleDateString('es-MX',
        { day: 'numeric', month: 'short', year: 'numeric' });
}

// RF-09: el documento solo se puede subir dentro del periodo que define la oficina.
function textoPeriodo(d) {
    // La carta de terminación tiene su propio flujo: Vinculación sube el Word,
    // el alumno lo descarga, lo firma y sube el PDF; Vinculación lo valida.
    if (d.tipo === 'CARTA_TERMINACION') {
        if (d.firmada) {
            return { texto: 'Carta validada por Vinculación. Servicio social LIBERADO.', clase: 'abierto' };
        }
        if (d.estatus === 'PENDIENTE' && d.documento_id) {
            return { texto: 'Carta recibida. En revisión por el Jefe de Vinculación.', clase: 'abierto' };
        }
        if (d.estatus === 'OBSERVADO') {
            return { texto: 'Vinculación observó tu carta. Corrige y sube otra versión.', clase: 'vencido' };
        }
        if (d.puede_subir) {
            return {
                texto: 'Descarga la carta en Word, fírmala y súbela en PDF.',
                clase: 'abierto'
            };
        }
        if (d.subido_en) {
            return {
                texto: 'Vinculación ya subió la carta; se habilita al validar tus documentos.',
                clase: 'bloqueado'
            };
        }
        return {
            texto: 'El Jefe de Vinculación subirá la carta en Word al validarse tus documentos.',
            clase: 'bloqueado'
        };
    }
    if (d.abierto) {
        return {
            texto: `Periodo abierto: ${fechaCorta(d.fecha_inicio)} al ${fechaCorta(d.fecha_fin)}`,
            clase: 'abierto'
        };
    }
    if (d.motivo_bloqueo === 'NO_INICIADO') {
        return {
            texto: `Se habilita el ${fechaCorta(d.fecha_inicio)} (hasta el ${fechaCorta(d.fecha_fin)})`,
            clase: 'bloqueado'
        };
    }
    if (d.motivo_bloqueo === 'VENCIDO') {
        return { texto: `Periodo vencido el ${fechaCorta(d.fecha_fin)}`, clase: 'vencido' };
    }
    return { texto: 'Sin periodo definido por la Oficina de Servicio Social', clase: 'bloqueado' };
}

async function cargarDocumentos() {
    const cuerpo = document.getElementById('tabla-docs-body');
    try {
        const docs = await api('/api/alumno/documentos');
        if (docs.length === 0) {
            filaMensaje(cuerpo, 5, 'Debe seleccionar un programa de servicio social primero.');
            return;
        }
        cuerpo.replaceChildren();
        docs.forEach((d) => {
            const nombre = d.tipo === 'REPORTE_BIMESTRAL'
                ? `Reporte bimestral #${d.numero_reporte}` : (NOMBRE_DOCUMENTO[d.tipo] || d.tipo);

            const tdNombre = document.createElement('td');
            const fuerte = document.createElement('strong');
            fuerte.textContent = nombre;
            const periodo = textoPeriodo(d);
            const nota = document.createElement('small');
            nota.className = 'periodo-doc ' + periodo.clase;
            nota.textContent = periodo.texto;
            tdNombre.append(fuerte, document.createElement('br'), nota);

            const estatus = d.estatus;
            const tdEstatus = document.createElement('td');
            const insignia = document.createElement('span');
            insignia.className = 'badge-estatus ' + (CLASE_ESTATUS[estatus] || '');
            insignia.textContent = estatus.replace('_', ' ');
            tdEstatus.appendChild(insignia);

            const tdArchivo = document.createElement('td');
            const tdAccion = document.createElement('td');

            if (d.tipo === 'CARTA_TERMINACION') {
                // Primero se descarga el Word de Vinculación; luego se sube el
                // PDF firmado, que queda pendiente hasta que Vinculación lo valide.
                const nota = document.createElement('span');
                nota.className = 'texto-bloqueado';
                nota.textContent = d.firmada
                    ? 'PDF validado por Vinculación'
                    : d.estatus === 'PENDIENTE' && d.documento_id
                        ? 'En revisión por el Jefe de Vinculación'
                        : d.estatus === 'OBSERVADO'
                            ? 'Corrige el documento y sube una nueva versión'
                            : d.puede_subir
                                ? 'PDF firmado (máx. 5 MB)'
                                : 'Se habilita al validar sus documentos';
                tdArchivo.appendChild(nota);

                if (d.puede_descargar && d.carta_word_id) {
                    const enlace = document.createElement('a');
                    enlace.className = 'btn-descargar';
                    enlace.href = `/api/documentos/${d.carta_word_id}/archivo?descargar=1`;
                    enlace.textContent = 'Descargar Word';
                    tdAccion.appendChild(enlace);
                }

                if (d.documento_id) {
                    const ver = document.createElement('a');
                    ver.className = 'btn-descargar';
                    ver.href = `/api/documentos/${d.documento_id}/archivo?descargar=1`;
                    ver.textContent = d.firmada ? 'Ver carta validada' : 'Ver carta subida';
                    tdAccion.appendChild(ver);
                }

                if (d.puede_subir) {
                    const entrada = document.createElement('input');
                    entrada.type = 'file';
                    entrada.accept = 'application/pdf,.pdf';
                    tdArchivo.appendChild(entrada);

                    const boton = document.createElement('button');
                    boton.type = 'button';
                    boton.className = 'btn-subir';
                    boton.textContent = d.estatus === 'OBSERVADO'
                        ? 'Subir nueva versión' : 'Subir carta firmada';
                    boton.addEventListener('click', () => subirArchivo(d, entrada, boton));
                    tdAccion.appendChild(boton);
                } else if (!d.documento_id) {
                    const bloqueado = document.createElement('span');
                    bloqueado.className = 'texto-bloqueado';
                    bloqueado.textContent = 'No disponible';
                    tdAccion.appendChild(bloqueado);
                }

                const fila = document.createElement('tr');
                fila.append(tdNombre, tdEstatus, crearCelda(d.observaciones || 'Ninguna'),
                            tdArchivo, tdAccion);
                cuerpo.appendChild(fila);
                return;
            }

            // La plantilla se descarga siempre, sin importar la fecha.
            if (d.plantilla) {
                const enlace = document.createElement('a');
                enlace.className = 'btn-descargar';
                enlace.href = `/api/alumno/plantillas/${encodeURIComponent(d.tipo)}`
                    + `/archivo?numero_reporte=${d.numero_reporte}`;
                enlace.textContent = 'Descargar plantilla';
                tdAccion.appendChild(enlace);
            }

            if (d.estatus === 'VALIDADO') {
                const listo = document.createElement('span');
                listo.textContent = 'Completado';
                tdAccion.appendChild(listo);
            } else if (!d.abierto) {
                const bloqueado = document.createElement('span');
                bloqueado.className = 'texto-bloqueado';
                bloqueado.textContent = 'No disponible';
                tdAccion.appendChild(bloqueado);
            } else {
                const entrada = document.createElement('input');
                entrada.type = 'file';
                entrada.accept = 'application/pdf,.pdf';
                tdArchivo.appendChild(entrada);

                const boton = document.createElement('button');
                boton.type = 'button';
                boton.className = 'btn-subir';
                boton.textContent = 'Subir PDF';
                boton.addEventListener('click', () => subirArchivo(d, entrada, boton));
                tdAccion.appendChild(boton);
            }

            const tr = document.createElement('tr');
            tr.append(tdNombre, tdEstatus, crearCelda(d.observaciones || 'Ninguna'), tdArchivo, tdAccion);
            cuerpo.appendChild(tr);
        });
    } catch (e) {
        filaMensaje(cuerpo, 5, e.message);
    }
}

async function subirArchivo(doc, entrada, boton) {
    const archivo = entrada.files[0];
    if (!archivo) { alert('Seleccione un archivo PDF.'); return; }
    if (!archivo.name.toLowerCase().endsWith('.pdf')) { alert('Solo se permiten archivos PDF.'); return; }
    if (archivo.size > 5 * 1024 * 1024) { alert('El archivo supera los 5 MB permitidos.'); return; }

    const esCarta = doc.tipo === 'CARTA_TERMINACION';
    const pregunta = esCarta
        ? '¿Subir la carta de terminación firmada? Quedará pendiente hasta que el Jefe de Vinculación la valide.'
        : '¿Subir este documento?';
    if (!confirm(pregunta)) return;

    const datos = new FormData();
    datos.append('archivo', archivo);
    datos.append('tipo', doc.tipo);
    datos.append('numero_reporte', doc.numero_reporte);

    const textoOriginal = boton.textContent;
    boton.disabled = true;
    boton.textContent = 'Subiendo…';
    try {
        const r = await api('/api/alumno/documentos', { method: 'POST', body: datos });
        alert(r.mensaje || '¡Documento subido correctamente!');
        cargarDocumentos();
    } catch (e) {
        alert('Error al subir: ' + e.message);
        boton.disabled = false;
        boton.textContent = textoOriginal;
    }
}