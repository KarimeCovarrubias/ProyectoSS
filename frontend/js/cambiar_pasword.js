document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('form-cambiar-pass');
    const mensaje = document.getElementById('mensaje');
    const boton = document.getElementById('btn-submit');

    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault(); // EVITA QUE SE RECARGUE LA PÁGINA O SALGA EL ? EN LA URL

        const actual = document.getElementById('actual').value;
        const nueva = document.getElementById('nueva').value;
        const confirmacion = document.getElementById('confirmacion').value;

        mensaje.className = 'msg';
        mensaje.textContent = '';

        if (nueva !== confirmacion) {
            mensaje.textContent = 'La nueva contraseña y su confirmación no coinciden.';
            mensaje.className = 'msg error';
            return;
        }

        if (nueva.length < 10) {
            mensaje.textContent = 'La nueva contraseña debe tener al menos 10 caracteres.';
            mensaje.className = 'msg error';
            return;
        }

        boton.disabled = true;
        boton.textContent = 'Guardando…';

        try {
            const respuesta = await fetch('/api/cambiar-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ actual, nueva, confirmacion })
            });

            const data = await respuesta.json().catch(() => ({}));

            if (!respuesta.ok) {
                throw new Error(data.error?.mensaje || 'No se pudo actualizar la contraseña.');
            }

            mensaje.textContent = data.mensaje || '¡Contraseña actualizada correctamente! Redirigiendo...';
            mensaje.className = 'msg ok';

            // Al cambiarla con éxito, mandarlo al login para iniciar sesión limpio con su nueva contraseña
            setTimeout(() => {
                window.location.href = '/html/login.html';
            }, 1500);

        } catch (err) {
            mensaje.textContent = err.message || 'Error de conexión con el servidor.';
            mensaje.className = 'msg error';
            boton.disabled = false;
            boton.textContent = 'Guardar Nueva Contraseña';
        }
    });
});