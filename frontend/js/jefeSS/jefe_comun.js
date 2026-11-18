// Utilidades compartidas por las páginas del Jefe de Oficina de SS (carga sesion.js antes).

const NOMBRE_DOC = {
    CARTA_PRESENTACION: 'Carta de presentación',
    SOLICITUD: 'Solicitud de servicio social',
    CARTA_ACEPTACION: 'Carta de aceptación',
    MEMORIA_FINAL: 'Memoria final',
    CARTA_TERMINACION: 'Carta de terminación'
};
const CLASE_BADGE = {
    PENDIENTE: 'badge-pendiente', VALIDADO: 'badge-validado', OBSERVADO: 'badge-observado',
    DISPONIBLE: 'badge-validado', APROBADA: 'badge-validado', RECHAZADA: 'badge-observado',
    INACTIVO: 'badge-sin-subir'
};

// La BD guarda la fecha en UTC ("2026-11-15 22:30:00"); aquí se muestra en hora local.
function fechaLocal(texto) {
    if (!texto) return '—';
    const f = new Date(texto.replace(' ', 'T') + 'Z');
    return isNaN(f) ? texto : f.toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
}

function crearBoton(texto, clase, accion) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = clase;
    b.textContent = texto;
    b.addEventListener('click', accion);
    return b;
}

function crearBadge(estatus) {
    const s = document.createElement('span');
    s.className = 'badge-estatus ' + (CLASE_BADGE[estatus] || 'badge-sin-subir');
    s.textContent = estatus;
    return s;
}

// Muestra un texto en una caja .mensaje (tipo: 'ok' o 'error'). Sin texto la deja vacía.
function aviso(caja, texto, tipo) {
    caja.textContent = texto || '';
    caja.className = 'mensaje' + (texto && tipo ? ' ' + tipo : '');
}

// Ventana emergente con un formulario.
//   campos: [{ id, etiqueta, tipo: 'text'|'number'|'textarea'|'select', valor, opciones: [[valor, texto]],
//              requerido, min }]
//   alEnviar(valores): función async; si lanza un Error se muestra en la ventana y no se cierra.
function abrirModal({ titulo, descripcion, campos, textoBoton, alEnviar }) {
    const fondo = document.createElement('div');
    fondo.className = 'modal-fondo';
    const form = document.createElement('form');
    form.className = 'modal-caja';

    const h = document.createElement('h2');
    h.textContent = titulo;
    form.appendChild(h);
    if (descripcion) {
        const p = document.createElement('p');
        p.className = 'modal-desc';
        p.textContent = descripcion;
        form.appendChild(p);
    }

    const entradas = {};
    for (const c of campos) {
        const grupo = document.createElement('div');
        grupo.className = 'form-group';
        const etiqueta = document.createElement('label');
        etiqueta.textContent = c.etiqueta + (c.requerido ? ' *' : '');
        let entrada;
        if (c.tipo === 'textarea') {
            entrada = document.createElement('textarea');
        } else if (c.tipo === 'select') {
            entrada = document.createElement('select');
            for (const [valor, texto] of c.opciones || []) {
                const o = document.createElement('option');
                o.value = valor;
                o.textContent = texto;
                entrada.appendChild(o);
            }
        } else {
            entrada = document.createElement('input');
            entrada.type = c.tipo || 'text';
            if (c.min != null) entrada.min = c.min;
        }
        entrada.id = 'modal-' + c.id;
        etiqueta.htmlFor = entrada.id;
        if (c.valor != null) entrada.value = c.valor;
        entradas[c.id] = entrada;
        grupo.append(etiqueta, entrada);
        form.appendChild(grupo);
    }

    const msg = document.createElement('div');
    msg.className = 'mensaje';
    const botones = document.createElement('div');
    botones.className = 'modal-botones';
    const cancelar = crearBoton('Cancelar', 'btn-secundario', () => cerrar());
    const enviar = document.createElement('button');
    enviar.type = 'submit';
    enviar.className = 'btn-guardar';
    enviar.textContent = textoBoton || 'Guardar';
    botones.append(cancelar, enviar);
    form.append(msg, botones);
    fondo.appendChild(form);

    const alTeclear = (e) => { if (e.key === 'Escape') cerrar(); };
    function cerrar() {
        document.removeEventListener('keydown', alTeclear);
        fondo.remove();
    }
    document.addEventListener('keydown', alTeclear);
    fondo.addEventListener('mousedown', (e) => { if (e.target === fondo) cerrar(); });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const valores = {};
        for (const c of campos) {
            valores[c.id] = entradas[c.id].value.trim();
            if (c.requerido && !valores[c.id]) {
                aviso(msg, `"${c.etiqueta}" es obligatorio.`, 'error');
                entradas[c.id].focus();
                return;
            }
        }
        enviar.disabled = true;
        enviar.textContent = 'Guardando…';
        try {
            await alEnviar(valores);
            cerrar();
        } catch (err) {
            aviso(msg, err.message, 'error');
            enviar.disabled = false;
            enviar.textContent = textoBoton || 'Guardar';
        }
    });

    document.body.appendChild(fondo);
    const primera = form.querySelector('input, textarea, select');
    if (primera) primera.focus();
}
