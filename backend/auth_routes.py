import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from backend.db import conectar, registrar_bitacora, transaccion
from backend.seguridad import ROLES, error, login_requerido
from backend.validaciones import unir_nombre, validar_password

auth_bp = Blueprint("auth_bp", __name__)

MAX_INTENTOS = 3
MINUTOS_BLOQUEO = 15
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


@auth_bp.post("/api/login")
def login():
    datos = request.get_json(silent=True) or {}
    usuario = str(datos.get("usuario", "")).strip()
    contrasena = str(datos.get("contrasena", ""))
    if not usuario or not contrasena:
        return error("Debe capturar usuario y contraseña", 400)

    with transaccion() as con:
        fila = con.execute(
            "SELECT * FROM usuarios WHERE identificador = ? OR correo = ?",
            (usuario, usuario.lower())).fetchone()
        if fila is None:
            return error("Usuario o contraseña incorrectos", 401)

        ahora = datetime.now(timezone.utc)
        if fila["bloqueado_hasta"]:
            hasta = datetime.strptime(fila["bloqueado_hasta"], FORMATO_FECHA).replace(
                tzinfo=timezone.utc)
            if hasta > ahora:
                minutos = int((hasta - ahora).total_seconds() // 60) + 1
                return error(f"Cuenta bloqueada temporalmente. Intente de nuevo en {minutos} minuto(s)", 423)

        # Los alumnos usan su CURP como contraseña (la capturan en el Forms externo).
        # Se toleran minúsculas y espacios accidentales al escribirla.
        candidatas = [contrasena]
        if fila["rol"] == "ALUMNO":
            candidatas.append(contrasena.strip().upper())
        valida = any(check_password_hash(fila["password_hash"], c) for c in candidatas)

        if not valida:
            intentos = fila["intentos_fallidos"] + 1
            if intentos >= MAX_INTENTOS:
                hasta = (ahora + timedelta(minutes=MINUTOS_BLOQUEO)).strftime(FORMATO_FECHA)
                con.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = ? WHERE id = ?",
                            (hasta, fila["id"]))
                registrar_bitacora(con, fila["id"], "CUENTA_BLOQUEADA", f"{MAX_INTENTOS} intentos fallidos")
                return error(f"Demasiados intentos fallidos. La cuenta se bloqueó {MINUTOS_BLOQUEO} minutos", 423)
            con.execute("UPDATE usuarios SET intentos_fallidos = ? WHERE id = ?", (intentos, fila["id"]))
            registrar_bitacora(con, fila["id"], "LOGIN_FALLIDO")
            return error("Usuario o contraseña incorrectos", 401)

        if not fila["activo"] or fila["rol"] not in ROLES:
            return error("No cuenta con permisos de acceso", 403)

        con.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = ?",
                    (fila["id"],))
        registrar_bitacora(con, fila["id"], "LOGIN")

        nombre = unir_nombre(fila["nombre"], fila["apellido_paterno"], fila["apellido_materno"])
        session.clear()
        session.permanent = True
        session.update(
            sid=uuid.uuid4().hex,
            usuario_id=fila["id"],
            identificador=fila["identificador"],
            nombre=nombre,                       # nombre completo, para mostrar
            rol=fila["rol"],
        )
        debe_cambiar = bool(fila["debe_cambiar_password"])
        return jsonify({
            "usuario": {
                "id": fila["id"],
                "identificador": fila["identificador"],
                "nombre": nombre,
                "nombre_completo": nombre,
                "nombre_pila": fila["nombre"],
                "apellido_paterno": fila["apellido_paterno"],
                "apellido_materno": fila["apellido_materno"],
                "correo": fila["correo"],
                "rol": fila["rol"],
                "debe_cambiar_password": debe_cambiar,
            },
            "debe_cambiar_password": debe_cambiar,
        })


@auth_bp.post("/api/logout")
@login_requerido()
def logout():
    with transaccion() as con:
        registrar_bitacora(con, session["usuario_id"], "LOGOUT")
    session.clear()
    return jsonify({"ok": True})


@auth_bp.get("/api/sesion")
@login_requerido()
def sesion_actual():
    with closing(conectar()) as con:
        fila = con.execute(
            """SELECT id, identificador, nombre, apellido_paterno, apellido_materno,
                      correo, rol, activo, debe_cambiar_password
               FROM usuarios WHERE id = ?""", (session["usuario_id"],)).fetchone()
    if fila is None or not fila["activo"]:
        session.clear()
        return error("Su sesión ya no es válida. Vuelva a iniciar sesión.", 401)

    nombre = unir_nombre(fila["nombre"], fila["apellido_paterno"], fila["apellido_materno"])
    debe_cambiar = bool(fila["debe_cambiar_password"])
    return jsonify({
        "usuario": {
            "id": fila["id"],
            "identificador": fila["identificador"],
            "nombre": nombre,
            "nombre_completo": nombre,
            "nombre_pila": fila["nombre"],
            "apellido_paterno": fila["apellido_paterno"],
            "apellido_materno": fila["apellido_materno"],
            "correo": fila["correo"],
            "rol": fila["rol"],
            "debe_cambiar_password": debe_cambiar,
        },
        "debe_cambiar_password": debe_cambiar,
    })


@auth_bp.post("/api/cambiar-password")
@login_requerido()
def cambiar_password():
    datos = request.get_json(silent=True) or {}
    actual = datos.get("actual", "")
    nueva = datos.get("nueva", "")
    confirmacion = datos.get("confirmacion", "")

    if not actual or not nueva or not confirmacion:
        return error("Todos los campos son obligatorios", 400)
    if nueva != confirmacion:
        return error("La nueva contraseña y la confirmación no coinciden", 400)
    if nueva == actual:
        return error("La nueva contraseña debe ser distinta de la actual", 400)
    err_pass = validar_password(nueva)
    if err_pass:
        return error(err_pass, 400)

    usuario_id = session["usuario_id"]
    with transaccion() as con:
        fila = con.execute("SELECT password_hash FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        if not fila or not check_password_hash(fila["password_hash"], actual):
            return error("La contraseña actual no es correcta", 400)

        con.execute(
            "UPDATE usuarios SET password_hash = ?, debe_cambiar_password = 0 WHERE id = ?",
            (generate_password_hash(nueva), usuario_id))
        registrar_bitacora(con, usuario_id, "CAMBIO_PASSWORD", "Actualizó su contraseña")

    return jsonify({"ok": True, "mensaje": "Contraseña actualizada correctamente"})