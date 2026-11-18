from functools import wraps
from flask import jsonify, session

ROLES = ["ALUMNO", "JEFE_OFICINA_SS", "JEFE_VINCULACION", "ADMINISTRADOR"]


def error(mensaje, codigo=400, clave=None):
    """Respuesta de error uniforme. 'clave' es un código que el frontend puede interpretar."""
    return jsonify({"error": {"mensaje": mensaje, "codigo": clave}}), codigo


def login_requerido(*roles):
    """Exige sesión y, opcionalmente, uno de los roles indicados.

    Se acepta tanto ``login_requerido("ALUMNO")`` como
    ``login_requerido("ALUMNO", "JEFE_OFICINA_SS")`` o una lista.
    """
    permitidos = []
    for rol in roles:
        if isinstance(rol, (list, tuple, set)):
            permitidos.extend(rol)
        else:
            permitidos.append(rol)

    def decorador(f):
        @wraps(f)
        def envuelta(*args, **kwargs):
            if "usuario_id" not in session:
                return error("No ha iniciado sesión", 401)

            if permitidos and session.get("rol") not in permitidos:
                return error("No cuenta con los permisos necesarios", 403)

            return f(*args, **kwargs)
        return envuelta
    return decorador