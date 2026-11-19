# Rutas para consultar o descargar documentos protegidos del sistema
from contextlib import closing
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, session

from backend.comun import carta_terminacion_habilitada
from backend.db import conectar
from backend.rutas import archivos
from backend.seguridad import error, login_requerido

MIMETYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

bp = Blueprint("documentos", __name__, url_prefix="/api")


@bp.get("/documentos/<int:documento_id>/archivo")
@login_requerido("ALUMNO", "JEFE_OFICINA_SS", "JEFE_VINCULACION", "ADMINISTRADOR")
def ver_documento(documento_id):
    with closing(conectar()) as con:
        doc = con.execute(
            "SELECT d.tipo, d.nombre_original, d.ruta_archivo, d.estatus, d.servicio_id, "
            "d.subido_por, s.alumno_id FROM documentos d "
            "JOIN servicios_sociales s ON s.id = d.servicio_id "
            "WHERE d.id = ?", (documento_id,)).fetchone()
        if doc is None:
            return error("El documento no existe", 404)

        rol = session["rol"]
        if rol == "ALUMNO" and doc["alumno_id"] != session["usuario_id"]:
            return error("Acceso denegado", 403)
        if rol == "JEFE_VINCULACION" and doc["tipo"] not in ("CARTA_TERMINACION", "MEMORIA_FINAL"):
            return error("Acceso denegado", 403)
        if rol == "ALUMNO" and doc["tipo"] == "CARTA_TERMINACION":
            # El alumno puede ver su propio PDF firmado. El Word que subió
            # Vinculación solo se descarga cuando su expediente está validado.
            if doc["subido_por"] != session["usuario_id"]:
                habilitada = carta_terminacion_habilitada(con, doc["servicio_id"])
                if not habilitada or habilitada["id"] != documento_id:
                    return error("La carta de terminación estará disponible para descarga "
                                 "cuando la Oficina de Servicio Social valide todos sus "
                                 "documentos.", 409)

    ruta = archivos.ruta_segura(doc["ruta_archivo"])
    if ruta is None or not ruta.is_file():
        return error("No se puede visualizar el documento", 404)
    mimetype = MIMETYPES.get(Path(doc["ruta_archivo"]).suffix.lower(),
                             "application/octet-stream")
    respuesta = send_file(ruta, mimetype=mimetype,
                          as_attachment=(request.args.get("descargar") == "1"
                                         or mimetype != "application/pdf"),
                          download_name=doc["nombre_original"])
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    return respuesta

# Consulta si el alumno ya tiene liberados y validados todos sus documentos para poder descargar su carta
@bp.get("/mi-carta-terminacion")
@login_requerido("ALUMNO")
def mi_carta_terminacion():
    with closing(conectar()) as con:
        servicio = con.execute(
            "SELECT id FROM servicios_sociales WHERE alumno_id = ? AND estatus <> 'BAJA' "
            "ORDER BY id DESC LIMIT 1", (session["usuario_id"],)).fetchone()
        if servicio is None:
            return jsonify({"disponible": False,
                            "mensaje": "No cuenta con un servicio social registrado."})
        fila = carta_terminacion_habilitada(con, servicio["id"])
    if fila is None:
        return jsonify({"disponible": False,
                        "mensaje": "La carta se habilita cuando todos sus documentos "
                                   "estén subidos y validados por la Oficina de Servicio Social."})
    return jsonify({"disponible": True, "documento_id": fila["id"],
                    "subida_en": fila["subido_en"],
                    "nombre_original": fila["nombre_original"]})
