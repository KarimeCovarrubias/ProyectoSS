// Plantillas en Word que el alumno descarga para llenar y devolver en PDF,
// y fechas de entrega (las mismas para todos los alumnos, RF-09).
document.addEventListener('DOMContentLoaded', async () => {
    const usuario = await requerirSesion('JEFE_OFICINA_SS');
    if (!usuario) return;
    document.getElementById('periodo-semana-inicio').value = fechaHoy();
    document.getElementById('btn-semana').addEventListener('click', aplicarSemana);
    cargarPlantillas();
});

const ESTADO_PERIODO = {
    ABIERTO: { texto: 'Abierto', clase: 'badge-validado' },
    PROGRAMADO: { texto: 'Programado', clase: 'badge-pendiente' },
    VENCIDO: { texto: 'Vencido', clase: 'badge-observado' },
    SIN_PERIODO: { texto: 'Sin fecha', clase: 'badge-sin-subir' }
};

function fechaHoy() {
    const f = new Date();
    return [f.getFullYear(), String(f.getMonth() + 1).padStart(2, '0'),
            String(f.getDate()).padStart(2, '0')].join('-');
}

function sumarDias(iso, dias) {
    const [a, m, d] = iso.split('-').map(Number);
    const f = new Date(a, m - 1, d + dias);
    return [f.getFullYear(), String(f.getMonth() + 1).padStart(2, '0'),
            String(f.getDate()).padStart(2, '0')].join('-');
}

async function cargarPlantillas() {
    const cuerpo = document.getElementById('tabla-plantillas-body');
    try {
        const [lista, periodos] = await Promise.all([
            api('/api/jefe/plantillas'),
            api('/api/jefe/periodos')
        ]);
        // Un documento puede tener varias fechas (los reportes bimestrales son 3).
        const porTipo = new Map();
        for (const p of periodos) {
            if (!porTipo.has(p.tipo)) porTipo.set(p.tipo, []);
            porTipo.get(p.tipo).push(p);
        }

        cuerpo.replaceChildren();
        for (const p of lista) {
            const tdActual = document.createElement('td');
            if (p.nombre_archivo) {
                const enlace = document.createElement('a');
                enlace.href = `/api/jefe/plantillas/${encodeURIComponent(p.tipo)}/archivo`;
                enlace.textContent = p.nombre_archivo;
                const fecha = document.createElement('small');
                fecha.textContent = `Subida: ${fechaLocal(p.subido_en)}`;
                tdActual.append(enlace, document.createElement('br'), fecha);
            } else {
                tdActual.textContent = 'Sin plantilla (el alumno no verá botón de descarga)';
            }

            // Fechas de entrega: iguales para todos los alumnos.
            const tdFechas = document.createElement('td');
            tdFechas.className = 'celda-fechas';
            for (const periodo of (porTipo.get(p.tipo) || [])) {
                tdFechas.appendChild(grupoFecha(periodo));
            }

            const entrada = document.createElement('input');
            entrada.type = 'file';
            entrada.accept = '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document';
            const tdArchivo = document.createElement('td');
            tdArchivo.appendChild(entrada);

            const boton = crearBoton(p.nombre_archivo ? 'Reemplazar' : 'Subir', 'btn-subir',
                                     () => subirPlantilla(p, entrada, boton));
            const tdAccion = document.createElement('td');
            tdAccion.appendChild(boton);

            const tr = document.createElement('tr');
            tr.append(crearCelda(p.titulo), tdActual, tdFechas, tdArchivo, tdAccion);
            cuerpo.appendChild(tr);
        }
    } catch (e) {
        filaMensaje(cuerpo, 5, e.message);
    }
}

// Bloque de fechas de un documento (inicio, fin, estado y botón Guardar).
function grupoFecha(p) {
    const contenedor = document.createElement('div');
    contenedor.className = 'grupo-fecha';

    const titulo = document.createElement('span');
    titulo.className = 'grupo-fecha-titulo';
    titulo.textContent = p.tipo === 'REPORTE_BIMESTRAL'
        ? `Reporte bimestral #${p.numero_reporte}` : 'Entrega del documento';

    const inicio = document.createElement('input');
    inicio.type = 'date';
    inicio.value = p.fecha_inicio || '';
    inicio.title = 'Desde cuándo pueden subir (todos los alumnos)';

    const fin = document.createElement('input');
    fin.type = 'date';
    fin.value = p.fecha_fin || '';
    fin.title = 'Hasta cuándo pueden subir (todos los alumnos)';

    // Al elegir el inicio se propone una semana completa (7 días).
    inicio.addEventListener('change', () => {
        if (inicio.value && !fin.value) fin.value = sumarDias(inicio.value, 6);
    });

    const estado = ESTADO_PERIODO[p.estado] || ESTADO_PERIODO.SIN_PERIODO;
    const insignia = document.createElement('span');
    insignia.className = 'badge-estatus ' + estado.clase;
    insignia.textContent = estado.texto;

    const guardar = crearBoton('Guardar', 'btn-guardar',
                               () => guardarPeriodo(p, inicio, fin));

    const rango = document.createElement('span');
    rango.className = 'grupo-fecha-rango';
    rango.append(inicio, document.createTextNode(' a '), fin);

    contenedor.append(titulo, rango, insignia, guardar);
    return contenedor;
}

async function guardarPeriodo(p, inicio, fin) {
    const mensaje = document.getElementById('mensaje');
    if (!inicio.value) {
        return aviso(mensaje, `Indique la fecha de inicio para "${p.titulo}".`, 'error');
    }
    try {
        const r = await api('/api/jefe/periodos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tipo: p.tipo,
                numero_reporte: p.numero_reporte,
                fecha_inicio: inicio.value,
                fecha_fin: fin.value || sumarDias(inicio.value, 6)
            })
        });
        aviso(mensaje, `${p.titulo}: ${r.mensaje} (aplica a todos los alumnos)`, 'ok');
        cargarPlantillas();
    } catch (e) {
        aviso(mensaje, e.message, 'error');
    }
}

async function aplicarSemana() {
    const mensaje = document.getElementById('mensaje');
    const inicio = document.getElementById('periodo-semana-inicio');
    if (!inicio.value) return aviso(mensaje, 'Indique la fecha de inicio de la semana.', 'error');
    if (!confirm('¿Programar una semana (7 días) para todos los documentos que aún no tienen fecha?')) return;
    try {
        const r = await api('/api/jefe/periodos/semana', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha_inicio: inicio.value })
        });
        aviso(mensaje, r.mensaje, 'ok');
        cargarPlantillas();
    } catch (e) {
        aviso(mensaje, e.message, 'error');
    }
}

async function subirPlantilla(p, entrada, boton) {
    const mensaje = document.getElementById('mensaje');
    const archivo = entrada.files[0];
    if (!archivo) return aviso(mensaje, 'Seleccione un archivo Word (.docx).', 'error');
    if (!archivo.name.toLowerCase().endsWith('.docx')) {
        return aviso(mensaje, 'Solo se permiten archivos Word (.docx).', 'error');
    }
    if (archivo.size > 5 * 1024 * 1024) return aviso(mensaje, 'El archivo supera los 5 MB permitidos.', 'error');
    if (!confirm(`¿Guardar esta plantilla para "${p.titulo}"?`)) return;

    const datos = new FormData();
    datos.append('tipo', p.tipo);
    datos.append('archivo', archivo);
    boton.disabled = true;
    try {
        const r = await api('/api/jefe/plantillas', { method: 'POST', body: datos });
        aviso(mensaje, r.mensaje, 'ok');
        cargarPlantillas();
    } catch (e) {
        aviso(mensaje, e.message, 'error');
        boton.disabled = false;
    }
}
