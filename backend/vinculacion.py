"""Rutas del Jefe del Departamento de Vinculación.

- Sube la carta de terminación FIRMADA de los alumnos que concluyeron su servicio.
- Genera e imprime la constancia de terminación con folio único (RF-10, CU12).
"""
from __future__ import annotations

import uuid
from contextlib import closing
from datetime import date
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, session

from backend.comun import NOMBRE_SQL, documentos_faltantes, horas_acumuladas, notificar
from backend.db import conectar, registrar_bitacora, transaccion
from backend.documentos_word import generar_docx
from backend.rutas import archivos
from backend.seguridad import error, login_requerido
from backend import validaciones as v

bp = Blueprint("vinculacion", __name__, url_prefix="/api/vinculacion")
solo_vinculacion = login_requerido("JEFE_VINCULACION")

POR_PAGINA = 15

# La carta "vigente" para Vinculación es la que subió y validó el propio Jefe de
# Vinculación (no la propuesta que el alumno generó y el Jefe de SS validó).
UNION_CARTA = ("LEFT JOIN documentos d ON d.servicio_id = s.id "
               "AND d.tipo = 'CARTA_TERMINACION' AND d.estatus = 'VALIDADO' "
               "AND d.subido_por IN (SELECT v.id FROM usuarios v "
               "                     WHERE v.rol = 'JEFE_VINCULACION')")


def _escapar_like(texto):
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------- Resumen
@bp.get("/resumen")
@solo_vinculacion
def resumen():
    with closing(conectar()) as con:
        concluidos, subidas = con.execute(
            "SELECT COUNT(*), COUNT(d.id) FROM servicios_sociales s "
            f"{UNION_CARTA} WHERE s.estatus = 'CONCLUIDO'").fetchone()
        pendientes = [dict(f) for f in con.execute(
            f"SELECT s.id AS servicio_id, {NOMBRE_SQL} AS nombre, u.identificador, s.fecha_fin "
            "FROM servicios_sociales s JOIN usuarios u ON u.id = s.alumno_id "
            f"{UNION_CARTA} WHERE s.estatus = 'CONCLUIDO' AND d.id IS NULL "
            "ORDER BY s.fecha_fin, s.id LIMIT 5")]
        recientes = [dict(f) for f in con.execute(
            f"SELECT {NOMBRE_SQL} AS nombre, u.identificador, d.subido_en "
            "FROM documentos d JOIN servicios_sociales s ON s.id = d.servicio_id "
            "JOIN usuarios u ON u.id = s.alumno_id "
            "WHERE d.tipo = 'CARTA_TERMINACION' AND d.estatus = 'VALIDADO' "
            "AND d.subido_por IN (SELECT v.id FROM usuarios v "
            "                     WHERE v.rol = 'JEFE_VINCULACION') "
            "ORDER BY d.id DESC LIMIT 5")]
        constancias = con.execute("SELECT COUNT(*) FROM constancias").fetchone()[0]
    return jsonify({"concluidos": concluidos, "cartas_subidas": subidas,
                    "cartas_pendientes": concluidos - subidas,
                    "constancias_emitidas": constancias,
                    "pendientes": pendientes, "recientes": recientes})


# ---------------------------------------------------------------- Listado
@bp.get("/servicios")
@solo_vinculacion
def listar_servicios():
    """Servicios concluidos, con búsqueda (?q=), filtro (?estado=pendientes|subidas)
    y paginación (?pagina=). Primero van los que aún no tienen carta firmada."""
    q = request.args.get("q", "").strip()
    estado = request.args.get("estado", "").strip()
    try:
        pagina = max(int(request.args.get("pagina", "1")), 1)
    except ValueError:
        pagina = 1

    condiciones, parametros = ["s.estatus = 'CONCLUIDO'"], []
    if q:
        patron = f"%{_escapar_like(q)}%"
        condiciones.append(f"({NOMBRE_SQL} LIKE ? ESCAPE '\\' OR u.identificador LIKE ? ESCAPE '\\')")
        parametros += [patron, patron]
    if estado == "pendientes":
        condiciones.append("d.id IS NULL")
    elif estado == "subidas":
        condiciones.append("d.id IS NOT NULL")
    donde = "WHERE " + " AND ".join(condiciones)
    desde = ("FROM servicios_sociales s "
             "JOIN usuarios u ON u.id = s.alumno_id "
             "JOIN alumnos a ON a.usuario_id = s.alumno_id "
             "JOIN programas p ON p.id = s.programa_id "
             f"{UNION_CARTA}")

    with closing(conectar()) as con:
        total = con.execute(f"SELECT COUNT(*) {desde} {donde}", parametros).fetchone()[0]
        paginas = max(-(-total // POR_PAGINA), 1)
        pagina = min(pagina, paginas)
        filas = con.execute(
            f"SELECT s.id AS servicio_id, {NOMBRE_SQL} AS nombre, u.identificador, a.carrera, "
            "       p.nombre AS programa, s.fecha_fin, "
            "       d.id AS documento_id, d.version, d.subido_en, d.nombre_original "
            f"{desde} {donde} "
            "ORDER BY (d.id IS NOT NULL), s.fecha_fin, s.id LIMIT ? OFFSET ?",
            parametros + [POR_PAGINA, (pagina - 1) * POR_PAGINA]).fetchall()
    return jsonify({"servicios": [dict(f) for f in filas],
                    "total": total, "pagina": pagina, "paginas": paginas})


# ---------------------------------------------------------------- Subir carta
@bp.post("/servicios/<int:servicio_id>/carta")
@solo_vinculacion
def subir_carta(servicio_id):
    """Sube (o reemplaza) la carta de terminación firmada. Solo PDF, máx. 5 MB."""
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        return error("Seleccione el archivo PDF de la carta de terminación firmada")
    problema = v.validar_pdf(archivo.filename, archivos.tamano(archivo))
    if not problema and not archivos.es_pdf(archivo):
        problema = "Archivo no válido: el archivo no es un PDF"
    if problema:
        return error(problema)

    guardado = None
    try:
        with transaccion() as con:
            servicio = con.execute(
                "SELECT s.alumno_id, s.estatus, u.nombre, u.apellido_paterno, "
                "u.apellido_materno FROM servicios_sociales s "
                "JOIN usuarios u ON u.id = s.alumno_id WHERE s.id = ?",
                (servicio_id,)).fetchone()
            if servicio is None:
                return error("El servicio social no existe", 404)
            if servicio["estatus"] != "CONCLUIDO":
                return error("Solo se puede subir la carta de un servicio concluido", 409)

            version = con.execute(
                "SELECT COALESCE(MAX(version), 0) FROM documentos "
                "WHERE servicio_id = ? AND tipo = 'CARTA_TERMINACION'",
                (servicio_id,)).fetchone()[0] + 1
            guardado, relativa = archivos.guardar(archivo, "cartas")
            con.execute(
                "UPDATE documentos SET estatus = 'REEMPLAZADO' "
                "WHERE servicio_id = ? AND tipo = 'CARTA_TERMINACION' "
                "AND estatus <> 'REEMPLAZADO'", (servicio_id,))
            con.execute(
                "INSERT INTO documentos (servicio_id, tipo, numero_reporte, version, estatus, "
                "nombre_original, ruta_archivo, tamano_bytes, subido_por, revisado_por, "
                "revisado_en) VALUES (?, 'CARTA_TERMINACION', 0, ?, 'VALIDADO', ?, ?, ?, ?, ?, "
                "datetime('now'))",
                (servicio_id, version, Path(archivo.filename).name[:150], relativa,
                 guardado.stat().st_size, session["usuario_id"], session["usuario_id"]))
            nombre_alumno = " ".join(p for p in (servicio["nombre"], servicio["apellido_paterno"],
                                                 servicio["apellido_materno"]) if p)
            con.execute(
                "INSERT INTO notificaciones (usuario_id, mensaje) VALUES (?, ?)",
                (servicio["alumno_id"],
                 "Tu carta de terminación ya está disponible para descargar."
                 if version == 1 else
                 "Se actualizó tu carta de terminación. Ya puedes descargar la nueva versión."))
            registrar_bitacora(con, session["usuario_id"], "SUBIR_CARTA_TERMINACION",
                               f"{nombre_alumno} (servicio {servicio_id}), versión {version}")
    except Exception:
        if guardado:
            guardado.unlink(missing_ok=True)
        raise

    return jsonify({"mensaje": "Carta de terminación subida correctamente",
                    "version": version}), 201


# ------------------------------------------------------ Constancia (RF-10, CU12)
def _datos_constancia(con, servicio_id):
    return con.execute(
        f"""SELECT s.*, u.identificador, u.nombre, u.apellido_paterno, u.apellido_materno,
                   u.correo, a.curp, a.carrera, a.semestre, a.plan_estudios,
                   p.nombre AS programa, p.periodo, p.horas, p.actividades,
                   e.nombre AS dependencia, e.titular, e.domicilio, e.telefono
            FROM servicios_sociales s
            JOIN usuarios u ON u.id = s.alumno_id
            JOIN alumnos a ON a.usuario_id = s.alumno_id
            JOIN programas p ON p.id = s.programa_id
            JOIN empresas_receptoras e ON e.id = p.empresa_id
            WHERE s.id = ?""", (servicio_id,)).fetchone()


def _siguiente_folio(con):
    anio = date.today().year
    ultimo = con.execute(
        "SELECT folio FROM constancias WHERE folio LIKE ? ORDER BY id DESC LIMIT 1",
        (f"CST-{anio}-%",)).fetchone()
    consecutivo = 1
    if ultimo:
        try:
            consecutivo = int(ultimo["folio"].rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            consecutivo = 1
    while True:
        folio = f"CST-{anio}-{consecutivo:04d}"
        if not con.execute("SELECT 1 FROM constancias WHERE folio = ?", (folio,)).fetchone():
            return folio
        consecutivo += 1


@bp.get("/servicios/<int:servicio_id>/constancia")
@solo_vinculacion
def revisar_constancia(servicio_id):
    """Vista previa: indica si ya se puede generar y qué falta."""
    with closing(conectar()) as con:
        s = _datos_constancia(con, servicio_id)
        if s is None:
            return error("Servicio social no encontrado", 404)
        if s["estatus"] not in ("CONCLUIDO", "LIBERADO"):
            return jsonify({"puede": False, "faltantes": [],
                            "mensaje": "El servicio social aún no concluye"})
        emitida = con.execute("SELECT folio FROM constancias WHERE servicio_id = ?",
                              (servicio_id,)).fetchone()
        if emitida:
            return jsonify({"puede": True, "ya_emitida": True, "folio": emitida["folio"]})
        faltantes = documentos_faltantes(con, servicio_id)
        firmada = con.execute(
            "SELECT 1 FROM documentos d JOIN usuarios u ON u.id = d.subido_por "
            "WHERE d.servicio_id = ? AND d.tipo = 'CARTA_TERMINACION' "
            "AND d.estatus = 'VALIDADO' AND u.rol = 'JEFE_VINCULACION'",
            (servicio_id,)).fetchone()
        if not firmada:
            faltantes.append({"tipo": "CARTA_TERMINACION",
                              "numero_reporte": 0, "estatus": "SIN_FIRMA"})
        if horas_acumuladas(con, servicio_id) < s["horas_requeridas"]:
            faltantes.append({"tipo": "HORAS", "numero_reporte": 0,
                              "estatus": "INCOMPLETAS"})
    return jsonify({"puede": not faltantes, "faltantes": faltantes,
                    "mensaje": "Listo para emitir la constancia" if not faltantes
                    else "Faltan requisitos para emitir la constancia"})


@bp.post("/servicios/<int:servicio_id>/constancia")
@solo_vinculacion
def emitir_constancia(servicio_id):
    """Genera el .docx de la constancia y registra el folio único."""
    guardado = None
    try:
        with transaccion() as con:
            s = _datos_constancia(con, servicio_id)
            if s is None:
                return error("Servicio social no encontrado", 404)
            if s["estatus"] == "BAJA":
                return error("No se emite constancia de un servicio dado de baja", 409)
            if s["estatus"] not in ("CONCLUIDO", "LIBERADO"):
                return error("El servicio social aún no concluye", 409)

            emitida = con.execute("SELECT * FROM constancias WHERE servicio_id = ?",
                                  (servicio_id,)).fetchone()
            if emitida:
                return jsonify({"ok": True, "ya_emitida": True, "folio": emitida["folio"],
                                "mensaje": "La constancia ya había sido emitida",
                                "archivo": f"/api/vinculacion/constancias/{emitida['id']}/archivo"})

            firmada = con.execute(
                "SELECT 1 FROM documentos d JOIN usuarios u ON u.id = d.subido_por "
                "WHERE d.servicio_id = ? AND d.tipo = 'CARTA_TERMINACION' "
                "AND d.estatus = 'VALIDADO' AND u.rol = 'JEFE_VINCULACION'",
                (servicio_id,)).fetchone()
            if not firmada:
                return error("Falta subir la carta de terminación firmada por Vinculación", 409)
            if horas_acumuladas(con, servicio_id) < s["horas_requeridas"]:
                return error("No se puede emitir: las horas del servicio están incompletas", 409)
            faltantes = documentos_faltantes(con, servicio_id)
            if faltantes:
                return error("No se puede emitir: hay documentos faltantes o sin validar", 409,
                             clave="DOCUMENTOS_FALTANTES")

            folio = _siguiente_folio(con)
            datos = {
                "alumno_nombre": " ".join(p for p in (s["nombre"], s["apellido_paterno"],
                                                      s["apellido_materno"]) if p),
                "nombre": s["nombre"], "apellido_paterno": s["apellido_paterno"],
                "apellido_materno": s["apellido_materno"], "control": s["identificador"],
                "curp": s["curp"], "carrera": s["carrera"], "semestre": s["semestre"],
                "plan": {"NUEVO": "Plan nuevo", "ANTIGUO": "Plan antiguo"}.get(
                    s["plan_estudios"], "Por definir"),
                "programa": s["programa"], "dependencia": s["dependencia"],
                "responsable": s["titular"], "domicilio": s["domicilio"],
                "telefono": s["telefono"], "periodo": s["periodo"], "horas": s["horas"],
                "horas_requeridas": s["horas_requeridas"],
                "horas_acumuladas": horas_acumuladas(con, servicio_id),
                "actividades": s["actividades"], "folio": folio,
                "lugar_fecha": "Culiacán, Sinaloa, a " + date.today().strftime("%d/%m/%Y"),
            }
            contenido = generar_docx("CONSTANCIA", datos)

            carpeta = archivos.UPLOADS / "constancias"
            carpeta.mkdir(parents=True, exist_ok=True)
            guardado = carpeta / f"{uuid.uuid4().hex}.docx"
            guardado.write_bytes(contenido)
            relativa = f"constancias/{guardado.name}"

            constancia_id = con.execute(
                "INSERT INTO constancias (servicio_id, folio, ruta_archivo, emitida_por) "
                "VALUES (?, ?, ?, ?)",
                (servicio_id, folio, relativa, session["usuario_id"])).lastrowid
            con.execute(
                "UPDATE servicios_sociales SET estatus = 'LIBERADO', "
                "fecha_fin = COALESCE(fecha_fin, ?), actualizado_en = datetime('now') "
                "WHERE id = ?", (date.today().isoformat(), servicio_id))
            notificar(con, s["alumno_id"],
                      f"Se emitió su constancia de terminación del servicio social. "
                      f"Folio: {folio}.")
            registrar_bitacora(con, session["usuario_id"], "EMITIR_CONSTANCIA",
                               f"Servicio {servicio_id}, folio {folio}")
    except Exception:
        if guardado:
            guardado.unlink(missing_ok=True)
        raise

    return jsonify({"ok": True, "id": constancia_id, "folio": folio,
                    "mensaje": "Constancia generada correctamente",
                    "archivo": f"/api/vinculacion/constancias/{constancia_id}/archivo"})


@bp.get("/constancias")
@solo_vinculacion
def listar_constancias():
    with closing(conectar()) as con:
        filas = con.execute(
            f"""SELECT c.id, c.folio, c.emitida_en, s.id AS servicio_id,
                       {NOMBRE_SQL} AS alumno_nombre, u.identificador, a.carrera,
                       p.nombre AS programa, p.periodo
                FROM constancias c
                JOIN servicios_sociales s ON s.id = c.servicio_id
                JOIN usuarios u ON u.id = s.alumno_id
                JOIN alumnos a ON a.usuario_id = u.id
                JOIN programas p ON p.id = s.programa_id
                ORDER BY c.id DESC""").fetchall()
    return jsonify([dict(f) for f in filas])


@bp.get("/constancias/<int:constancia_id>/archivo")
@solo_vinculacion
def descargar_constancia(constancia_id):
    with closing(conectar()) as con:
        fila = con.execute(
            "SELECT c.folio, c.ruta_archivo, u.nombre, u.apellido_paterno, "
            "u.apellido_materno FROM constancias c "
            "JOIN servicios_sociales s ON s.id = c.servicio_id "
            "JOIN usuarios u ON u.id = s.alumno_id WHERE c.id = ?",
            (constancia_id,)).fetchone()
    if fila is None:
        return error("Constancia no encontrada", 404)
    ruta = archivos.ruta_segura(fila["ruta_archivo"])
    if not ruta or not ruta.is_file():
        return error("El archivo de la constancia no está disponible", 404)
    nombre = "_".join(p for p in (fila["nombre"], fila["apellido_paterno"],
                                  fila["apellido_materno"]) if p)
    return send_file(
        ruta, as_attachment=True, download_name=f"constancia_{fila['folio']}_{nombre}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
