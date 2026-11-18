// Inicio de sesión (CU01).
function mostrarMensaje(texto) {
    const caja = document.getElementById('login-msg');
    if (caja) caja.textContent = texto;
    else alert(texto);
}

async function handleLogin(event) {
    event.preventDefault();
    mostrarMensaje('');

    const usuario = document.getElementById('login-user').value.trim();
    const contrasena = document.getElementById('login-pass').value;
    if (!usuario || !contrasena) {
        mostrarMensaje('Debe capturar usuario y contraseña');
        return;
    }

    try {
        const respuesta = await fetch('/api/login', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usuario, contrasena })
        });
        const datos = await respuesta.json().catch(() => ({}));

        if (!respuesta.ok) {
            mostrarMensaje(datos.error?.mensaje || 'Usuario o contraseña incorrectos.');
            return;
        }

        const inicio = {
            ALUMNO: '/html/alumno/inicio.html',
            JEFE_OFICINA_SS: '/html/jefeSS/inicio.html',
            JEFE_VINCULACION: '/html/jefeVinc/inicio.html',
            ADMINISTRADOR: '/html/admin/inicio.html'
        };
        window.location.href = inicio[datos.usuario?.rol] || '/html/login.html';
    } catch (e) {
        mostrarMensaje('No se pudo conectar con el servidor. Intente de nuevo.');
    }
}