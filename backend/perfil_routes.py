"""Datos personales y de contacto del PERSONAL (jefe de SS, jefe de Vinculación, administrador).

Los alumnos guardan teléfono y domicilio en la tabla `alumnos`; el personal no tiene dónde,
así que se crea (solo la primera vez) la tabla `contacto_personal`. No hace falta
tocar crear_bd.py ni correr migraciones.
"""
from flask import Blueprint, jsonify, request, session

from backend.db import registrar_bitacora, transaccion
from backend.seguridad import error, login_requerido

perfil_bp = Blueprint("perfil_bp", __name__)

ROLES_PERSONAL = ("JEFE_OFICINA_SS", "JEFE_VINCULACION", "ADMINISTRADOR")


def _preparar_tabla(con):
    con.execute(
        """CREATE TABLE IF NOT EXISTS contacto_personal (
               usuario_id     INTEGER PRIMARY KEY REFERENCES usuarios(id),
               telefono       TEXT,
               domicilio      TEXT,
               actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
           )""")


@perfil_bp.get("/api/personal/perfil")
@login_requerido()
def personal_perfil():
    if session.get("rol") not in ROLES_PERSONAL:
        return error("Esta sección es solo para el personal del sistema", 403)
    with transaccion() as con:
        _preparar_tabla(con)
        u = con.execute(
            """SELECT u.nombre, u.apellido_paterno, u.apellido_materno, u.correo, u.rol,
                      c.telefono, c.domicilio
               FROM usuarios u
               LEFT JOIN contacto_personal c ON c.usuario_id = u.id
               WHERE u.id = ?""", (session["usuario_id"],)).fetchone()
    if not u:
        return error("Usuario no encontrado", 404)
    return jsonify(dict(u))


@perfil_bp.patch("/api/personal/perfil")
@login_requerido()
def personal_actualizar_perfil():
    if session.get("rol") not in ROLES_PERSONAL:
        return error("Esta sección es solo para el personal del sistema", 403)
    d = request.get_json(silent=True) or {}
    telefono = str(d.get("telefono", "")).strip()
    domicilio = str(d.get("domicilio", "")).strip()
    if telefono and not (telefono.isdigit() and len(telefono) == 10):
        return error("El teléfono debe tener 10 dígitos", 400)
    if not domicilio:
        return error("El domicilio es obligatorio", 400)
    if len(domicilio) > 200:
        return error("El domicilio no puede pasar de 200 caracteres", 400)

    with transaccion() as con:
        _preparar_tabla(con)
        con.execute(
            """INSERT INTO contacto_personal (usuario_id, telefono, domicilio)
               VALUES (?, ?, ?)
               ON CONFLICT(usuario_id) DO UPDATE SET telefono = excluded.telefono,
                   domicilio = excluded.domicilio, actualizado_en = datetime('now')""",
            (session["usuario_id"], telefono or None, domicilio))
        registrar_bitacora(con, session["usuario_id"], "ACTUALIZAR_PERFIL", "Datos de contacto")
    return jsonify({"ok": True, "mensaje": "Datos de contacto actualizados correctamente"})