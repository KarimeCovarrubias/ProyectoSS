"""Rutas del Jefe del Departamento de Vinculación.

- Sube la carta de terminación en Word (.docx) para que el alumno la descargue,
  la firme y entregue el PDF.
- Revisa el PDF firmado del alumno: al validarlo, el servicio queda LIBERADO;
  si lo observa, el alumno puede corregirlo y subir otra versión.
- Genera e imprime la constancia de terminación con folio único (RF-10, CU12).
"""
from __future__ import annotations

import uuid
from contextlib import closing
from datetime import date
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, session

from backend.comun import (
    NOMBRE_SQL, carta_firmada_alumno, documentos_faltantes, horas_acumuladas,
    listo_para_carta, notificar,
)
from backend.db import conectar, registrar_bitacora, transaccion
from backend.documentos_word import generar_docx
from backend.rutas import archivos
from backend.seguridad import error, login_requerido

bp = Blueprint("vinculacion", __name__, url_prefix="/api/vinculacion")
solo_vinculacion = login_requerido("JEFE_VINCULACION")

POR_PAGINA = 15
MAX_BYTES_CARTA = 5 * 1024 * 1024   # 5 MB

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
        filas = con.execute(
            f"SELECT s.id AS servicio_id, s.alumno_id, s.fecha_fin, {NOMBRE_SQL} AS nombre, "
            "       u.identificador, d.id AS documento_id, d.subido_en "
            "FROM servicios_sociales s JOIN usuarios u ON u.id = s.alumno_id "
            f"{UNION_CARTA} WHERE s.estatus <> 'BAJA' "
            "ORDER BY s.fecha_fin, s.id").fetchall()
        # Un alumno está listo cuando ya entregó y validó todo su expediente,
        # aunque el servicio siga en PENDIENTE (no depende del estatus previo).
        listos = [f for f in filas if listo_para_carta(con, f["servicio_id"])]
        subidas = [f for f in listos if f["documento_id"]]
        pendientes = [dict(f) for f in listos if not f["documento_id"]][:5]
        por_revisar = 0
        liberados = 0
        for fila in listos:
            pdf = carta_firmada_alumno(con, fila["servicio_id"], fila["alumno_id"])
            if pdf and pdf["estatus"] == "PENDIENTE":
                por_revisar += 1
            elif pdf and pdf["estatus"] == "VALIDADO":
                liberados += 1
        recientes = [dict(f) for f in con.execute(
            f"SELECT {NOMBRE_SQL} AS nombre, u.identificador, d.subido_en "
            "FROM documentos d JOIN servicios_sociales s ON s.id = d.servicio_id "
            "JOIN usuarios u ON u.id = s.alumno_id "
            "WHERE d.tipo = 'CARTA_TERMINACION' AND d.estatus = 'VALIDADO' "
            "AND d.subido_por IN (SELECT v.id FROM usuarios v "
            "                     WHERE v.rol = 'JEFE_VINCULACION') "
            "ORDER BY d.id DESC LIMIT 5")]
        constancias = con.execute("SELECT COUNT(*) FROM constancias").fetchone()[0]
    return jsonify({"concluidos": len(listos), "cartas_subidas": len(subidas),
                    "cartas_pendientes": len(listos) - len(subidas),
                    "por_revisar": por_revisar, "liberados": liberados,
                    "constancias_emitidas": constancias,
                    "pendientes": pendientes, "recientes": recientes})


# ---------------------------------------------------------------- Listado
@bp.get("/servicios")
@solo_vinculacion
def listar_servicios():
    """Servicios concluidos, con búsqueda (?q=), filtro (?estado=) y paginación
    (?pagina=). Primero van los que aún no tienen carta firmada.

    ``estado`` acepta: ``pendientes`` (sin Word), ``subidas`` (Word subido),
    ``por_revisar`` (PDF del alumno pendiente), ``observados`` y ``liberados``.
    """
    q = request.args.get("q", "").strip()
    estado = request.args.get("estado", "").strip()
    try:
        pagina = max(int(request.args.get("pagina", "1")), 1)
    except ValueError:
        pagina = 1

    condiciones, parametros = ["s.estatus <> 'BAJA'"], []
    if q:
        patron = f"%{_escapar_like(q)}%"
        condiciones.append(f"({NOMBRE_SQL} LIKE ? ESCAPE '\\' OR u.identificador LIKE ? ESCAPE '\\')")
        parametros += [patron, patron]
    donde = "WHERE " + " AND ".join(condiciones)
    desde = ("FROM servicios_sociales s "
             "JOIN usuarios u ON u.id = s.alumno_id "
             "JOIN alumnos a ON a.usuario_id = s.alumno_id "
             "JOIN programas p ON p.id = s.programa_id "
             f"{UNION_CARTA}")

    with closing(conectar()) as con:
        filas = con.execute(
            f"SELECT s.id AS servicio_id, s.alumno_id, {NOMBRE_SQL} AS nombre, "
            "       u.identificador, a.carrera, "
            "       p.nombre AS programa, s.fecha_fin, "
            "       d.id AS documento_id, d.version, d.subido_en, d.nombre_original "
            f"{desde} {donde} ORDER BY s.fecha_fin, s.id", parametros).fetchall()
        # Solo los alumnos cuyo expediente ya está completo (documentos validados
        # y horas cubiertas). No exigimos estatus CONCLUIDO: la Oficina pudo
        # validar todo sin haber cambiado el estatus del servicio.
        servicios = []
        for fila in filas:
            if not listo_para_carta(con, fila["servicio_id"]):
                continue
            if estado == "pendientes" and fila["documento_id"]:
                continue
            if estado == "subidas" and not fila["documento_id"]:
                continue
            item = dict(fila)
            pdf = carta_firmada_alumno(con, fila["servicio_id"], fila["alumno_id"])
            item["alumno_carta_id"] = pdf["id"] if pdf else None
            item["alumno_carta_estatus"] = pdf["estatus"] if pdf else "SIN_SUBIR"
            item["alumno_carta_version"] = pdf["version"] if pdf else None
            item["alumno_carta_subida_en"] = pdf["subido_en"] if pdf else None
            item["alumno_carta_nombre"] = pdf["nombre_original"] if pdf else None
            if estado == "por_revisar" and item["alumno_carta_estatus"] != "PENDIENTE":
                continue
            if estado == "observados" and item["alumno_carta_estatus"] != "OBSERVADO":
                continue
            if estado == "liberados" and item["alumno_carta_estatus"] != "VALIDADO":
                continue
            servicios.append(item)

        total = len(servicios)
        paginas = max(-(-total // POR_PAGINA), 1)
        pagina = min(pagina, paginas)
        inicio = (pagina - 1) * POR_PAGINA
        pagina_servicios = servicios[inicio:inicio + POR_PAGINA]
    return jsonify({"servicios": pagina_servicios,
                    "total": total, "pagina": pagina, "paginas": paginas})


# ---------------------------------------------------------------- Subir carta
@bp.post("/servicios/<int:servicio_id>/carta")
@solo_vinculacion
def subir_carta(servicio_id):
    """Sube (o reemplaza) la carta de terminación editable en Word (.docx).

    El alumno la descarga, la firma y sube el PDF. Ese PDF queda PENDIENTE
    hasta que Vinculación lo valide; solo entonces el servicio queda LIBERADO.
    Solo se permite cuando el expediente ya está validado.
    """
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        return error("Seleccione el archivo Word (.docx) de la carta de terminación")

    nombre_original = Path(archivo.filename).name[:150] or "carta_terminacion.docx"
    if not nombre_original.lower().endswith(".docx"):
        return error("Archivo no válido: la carta debe ser un documento Word (.docx)")
    tamano = archivos.tamano(archivo)
    if tamano <= 0 or tamano > MAX_BYTES_CARTA:
        return error("Archivo no válido: está vacío o excede 5 MB")
    if archivo.stream.read(4) != b"PK\x03\x04":   # un .docx es un zip
        return error("Archivo no válido: no es un documento de Word (.docx)")
    archivo.stream.seek(0)

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
            if not listo_para_carta(con, servicio_id):
                return error("La carta se habilita cuando el alumno tenga todos sus "
                             "documentos validados y sus horas completas.", 409)

            version = con.execute(
                "SELECT COALESCE(MAX(version), 0) FROM documentos "
                "WHERE servicio_id = ? AND tipo = 'CARTA_TERMINACION'",
                (servicio_id,)).fetchone()[0] + 1
            guardado, relativa = archivos.guardar(archivo, "cartas", ".docx")
            con.execute(
                "UPDATE documentos SET estatus = 'REEMPLAZADO' "
                "WHERE servicio_id = ? AND tipo = 'CARTA_TERMINACION' "
                "AND subido_por = ? AND estatus <> 'REEMPLAZADO'",
                (servicio_id, session["usuario_id"]))
            con.execute(
                "INSERT INTO documentos (servicio_id, tipo, numero_reporte, version, estatus, "
                "nombre_original, ruta_archivo, tamano_bytes, subido_por, revisado_por, "
                "revisado_en) VALUES (?, 'CARTA_TERMINACION', 0, ?, 'VALIDADO', ?, ?, ?, ?, ?, "
                "datetime('now'))",
                (servicio_id, version, nombre_original, relativa,
                 guardado.stat().st_size, session["usuario_id"], session["usuario_id"]))
            nombre_alumno = " ".join(p for p in (servicio["nombre"], servicio["apellido_paterno"],
                                                 servicio["apellido_materno"]) if p)
            con.execute(
                "INSERT INTO notificaciones (usuario_id, mensaje) VALUES (?, ?)",
                (servicio["alumno_id"],
                 "Tu carta de terminación ya está disponible para descargar en Word. "
                 "Descárgala, fírmala y súbela en PDF para que Vinculación la valide."
                 if version == 1 else
                 "Se actualizó tu carta de terminación. Descarga la nueva versión en Word, "
                 "fírmala y súbela en PDF para que Vinculación la valide."))
            registrar_bitacora(con, session["usuario_id"], "SUBIR_CARTA_TERMINACION",
                               f"{nombre_alumno} (servicio {servicio_id}), versión {version}")
    except Exception:
        if guardado:
            guardado.unlink(missing_ok=True)
        raise

    return jsonify({"mensaje": "Carta de terminación subida correctamente",
                    "version": version}), 201


# ------------------------------------- Revisión del PDF firmado por el alumno
@bp.post("/servicios/<int:servicio_id>/carta/revisar")
@solo_vinculacion
def revisar_carta_alumno(servicio_id):
    """VALIDA u OBSERVA el PDF firmado que subió el alumno.

    Al validarlo, el servicio social cambia a LIBERADO. Si se observa, el alumno
    recibe el comentario y puede subir una nueva versión.
    """
    datos = request.get_json(silent=True) or {}
    accion = str(datos.get("accion", "")).strip().upper()
    texto = str(datos.get("texto", "")).strip()
    if accion not in ("VALIDAR", "OBSERVAR"):
        return error("Acción no válida", 400)
    if accion == "OBSERVAR" and not texto:
        return error("Escriba las observaciones para que el alumno sepa qué corregir", 400)
    if len(texto) > 2000:
        return error("Las observaciones no pueden pasar de 2000 caracteres", 400)

    with transaccion() as con:
        servicio = con.execute(
            "SELECT alumno_id, estatus FROM servicios_sociales WHERE id = ?",
            (servicio_id,)).fetchone()
        if servicio is None:
            return error("El servicio social no existe", 404)
        if not listo_para_carta(con, servicio_id):
            return error("El expediente del alumno aún no está completo y validado.", 409)

        doc = con.execute(
            """SELECT d.id, d.estatus
               FROM documentos d JOIN usuarios u ON u.id = d.subido_por
               WHERE d.servicio_id = ? AND d.tipo = 'CARTA_TERMINACION'
                 AND d.estatus = 'PENDIENTE' AND u.rol = 'ALUMNO'
               ORDER BY d.version DESC, d.id DESC LIMIT 1""",
            (servicio_id,)).fetchone()
        if doc is None:
            return error("No hay una carta de terminación del alumno pendiente de revisión.",
                         409)

        nuevo = "VALIDADO" if accion == "VALIDAR" else "OBSERVADO"
        cursor = con.execute(
            "UPDATE documentos SET estatus = ?, revisado_por = ?, "
            "revisado_en = datetime('now') WHERE id = ? AND estatus = 'PENDIENTE'",
            (nuevo, session["usuario_id"], doc["id"]))
        if cursor.rowcount == 0:
            return error("La carta ya fue revisada o fue reemplazada por el alumno.", 409)

        if accion == "OBSERVAR":
            con.execute("INSERT INTO observaciones (documento_id, autor_id, texto) "
                        "VALUES (?, ?, ?)",
                        (doc["id"], session["usuario_id"], texto))
            con.execute(
                "INSERT INTO notificaciones (usuario_id, mensaje) VALUES (?, ?)",
                (servicio["alumno_id"],
                 "Tu carta de terminación firmada tiene observaciones: " + texto +
                 ". Corrige el documento y sube una nueva versión en PDF."))
        else:
            con.execute(
                "UPDATE servicios_sociales SET estatus = 'LIBERADO', "
                "fecha_fin = COALESCE(fecha_fin, ?), actualizado_en = datetime('now') "
                "WHERE id = ?", (date.today().isoformat(), servicio_id))
            con.execute(
                "INSERT INTO notificaciones (usuario_id, mensaje) VALUES (?, ?)",
                (servicio["alumno_id"],
                 "El Jefe de Vinculación validó tu carta de terminación firmada. "
                 "Tu servicio social quedó LIBERADO."))

        registrar_bitacora(con, session["usuario_id"], "REVISAR_CARTA_TERMINACION",
                           f"Servicio {servicio_id}, documento {doc['id']}: {nuevo}")

    if accion == "VALIDAR":
        return jsonify({"ok": True, "liberado": True,
                        "mensaje": "Carta validada. El servicio social quedó LIBERADO."})
    return jsonify({"ok": True, "liberado": False,
                    "mensaje": "Observaciones enviadas. El alumno puede subir otra versión."})


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


def _carta_firmada_por_alumno(con, servicio_id):
    """PDF firmado que el alumno subió después de descargar el Word de Vinculación."""
    return con.execute(
        "SELECT 1 FROM documentos d JOIN usuarios u ON u.id = d.subido_por "
        "WHERE d.servicio_id = ? AND d.tipo = 'CARTA_TERMINACION' "
        "AND d.estatus = 'VALIDADO' AND u.rol = 'ALUMNO'",
        (servicio_id,)).fetchone()


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
        if not _carta_firmada_por_alumno(con, servicio_id):
            faltantes.append({"tipo": "CARTA_TERMINACION",
                              "numero_reporte": 0, "estatus": "SIN_FIRMA_ALUMNO"})
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
            if not _carta_firmada_por_alumno(con, servicio_id):
                return error("Falta que el alumno suba su carta de terminación firmada en PDF", 409)
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
