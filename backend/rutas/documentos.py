"""Ver / descargar documentos guardados (los archivos NO son públicos: RNF-01, RNF-03)."""
from contextlib import closing

from flask import Blueprint, jsonify, request, send_file, session

from backend.db import conectar
from backend.rutas import archivos
from backend.seguridad import error, login_requerido

bp = Blueprint("documentos", __name__, url_prefix="/api")


@bp.get("/documentos/<int:documento_id>/archivo")
@login_requerido("ALUMNO", "JEFE_OFICINA_SS", "JEFE_VINCULACION", "ADMINISTRADOR")
def ver_documento(documento_id):
    """Abre el PDF en el navegador, o lo descarga con ?descargar=1.

    Permisos (RNF-03): el alumno solo ve SUS documentos; el Jefe de Oficina de SS ve
    los documentos del trámite; el Jefe de Vinculación solo la carta de terminación."""
    with closing(conectar()) as con:
        doc = con.execute(
            "SELECT d.tipo, d.nombre_original, d.ruta_archivo, d.estatus, s.alumno_id "
            "FROM documentos d JOIN servicios_sociales s ON s.id = d.servicio_id "
            "WHERE d.id = ?", (documento_id,)).fetchone()
    if doc is None:
        return error("El documento no existe", 404)

    rol = session["rol"]
    if rol == "ALUMNO" and doc["alumno_id"] != session["usuario_id"]:
        return error("Acceso denegado", 403)
    if rol == "JEFE_VINCULACION" and doc["tipo"] not in ("CARTA_TERMINACION", "MEMORIA_FINAL"):
        return error("Acceso denegado", 403)

    ruta = archivos.ruta_segura(doc["ruta_archivo"])
    if ruta is None or not ruta.is_file():
        return error("No se puede visualizar el documento", 404)
    respuesta = send_file(ruta, mimetype="application/pdf",
                          as_attachment=request.args.get("descargar") == "1",
                          download_name=doc["nombre_original"])
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    return respuesta


@bp.get("/mi-carta-terminacion")
@login_requerido("ALUMNO")
def mi_carta_terminacion():
    """Para la página del alumno: ¿ya está su carta firmada? Si sí, con qué id descargarla."""
    with closing(conectar()) as con:
        fila = con.execute(
            "SELECT d.id, d.subido_en FROM documentos d "
            "JOIN servicios_sociales s ON s.id = d.servicio_id "
            "JOIN usuarios u ON u.id = d.subido_por "
            "WHERE s.alumno_id = ? AND d.tipo = 'CARTA_TERMINACION' "
            "AND d.estatus = 'VALIDADO' AND u.rol = 'JEFE_VINCULACION' "
            "ORDER BY d.id DESC LIMIT 1", (session["usuario_id"],)).fetchone()
    if fila is None:
        return jsonify({"disponible": False})
    return jsonify({"disponible": True, "documento_id": fila["id"],
                    "subida_en": fila["subido_en"]})
