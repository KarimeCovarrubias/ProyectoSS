"""Rutas del Alumno (CU03..CU07, RF-05..RF-09, RF-16, RF-17)."""
from __future__ import annotations

import io
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, session
from werkzeug.utils import secure_filename

from backend.comun import (
    NOMBRE_SQL, TITULAR_SQL, avance_horas, carta_firmada_alumno,
    carta_terminacion, carta_terminacion_habilitada, documento_vigente,
    documentos_faltantes, documentos_requeridos, estado_periodo, horas_acumuladas,
    liberar_cupo, listo_para_carta, nombre_completo, notificar, notificar_rol,
    servicio_activo, servicio_del_alumno,
)
from backend.db import registrar_bitacora, transaccion
from backend.documentos_word import TITULOS, generar_docx
from backend.rutas import archivos
from backend.seguridad import error, login_requerido
from backend.validaciones import (
    MIN_PORCENTAJE_CREDITOS, validar_curp, validar_fecha, validar_nombres,
    validar_origen, validar_password, validar_pdf, validar_periodo, validar_plan,
    validar_telefono,
)

alumno_bp = Blueprint("alumno_bp", __name__)

TIPOS_DOCUMENTO = ("CARTA_PRESENTACION", "SOLICITUD", "CARTA_ACEPTACION",
                   "REPORTE_BIMESTRAL", "MEMORIA_FINAL", "CARTA_TERMINACION")


# ------------------------------------------------------------------ utilidades
def _alumno(con, uid):
    return con.execute(
        "SELECT u.id, u.identificador, u.nombre, u.apellido_paterno, u.apellido_materno, "
        "       u.correo, a.curp, a.carrera, a.semestre, a.telefono, a.domicilio, "
        "       a.plan_estudios, a.creditos, a.porcentaje_creditos "
        "FROM usuarios u JOIN alumnos a ON a.usuario_id = u.id WHERE u.id = ?", (uid,)).fetchone()


def _servicio_actual(con, uid):
    """Servicio más reciente que no esté dado de baja (aunque ya haya concluido)."""
    return con.execute(
        "SELECT * FROM servicios_sociales WHERE alumno_id = ? AND estatus <> 'BAJA' "
        "ORDER BY id DESC LIMIT 1", (uid,)).fetchone()


def _datos_programa(con, servicio):
    return con.execute(
        f"""SELECT p.id, p.nombre AS programa, p.tipo, p.origen, p.actividades, p.horas,
                  p.periodo, p.plan_estudios, e.nombre AS dependencia, e.titular,
                  e.titular_nombre, e.titular_apellido_paterno, e.titular_apellido_materno,
                  e.domicilio, e.telefono
           FROM programas p JOIN empresas_receptoras e ON p.empresa_id = e.id
           WHERE p.id = ?""", (servicio["programa_id"],)).fetchone()


def _bloqueo_solicitud(con, uid):
    """Motivo por el que el alumno aún NO puede elegir programa (o None)."""
    a = con.execute("SELECT plan_estudios, creditos, porcentaje_creditos, semestre "
                    "FROM alumnos WHERE usuario_id = ?", (uid,)).fetchone()
    if not a:
        return "No existe el expediente del alumno."
    asistencia = con.execute(
        "SELECT 1 FROM asistencias_induccion WHERE alumno_id = ? AND forms_completos = 1 "
        "ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    if not asistencia:
        return "Debe asistir al curso de inducción y llenar los FORMS antes de elegir un programa."
    if a["plan_estudios"] is None or a["creditos"] is None:
        return ("Su plan de servicio social y sus créditos aún no han sido capturados por el "
                "administrador. Acuda a la oficina de servicio social.")
    if (a["porcentaje_creditos"] or 0) < MIN_PORCENTAJE_CREDITOS:
        return f"Necesita al menos {MIN_PORCENTAJE_CREDITOS} % de créditos para solicitar el servicio."
    if servicio_activo(con, uid):
        return "Ya cuenta con un servicio social activo o pendiente."
    if con.execute("SELECT 1 FROM servicios_sociales WHERE alumno_id = ? "
                   "AND estatus IN ('CONCLUIDO','LIBERADO')", (uid,)).fetchone():
        return ("Ya concluyó su servicio social. No puede cargar otro programa ni "
                "registrar propuestas propias.")
    return None


MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")


def _fecha_larga(texto):
    """'2026-12-07' -> '7 de diciembre de 2026' (para los mensajes al alumno)."""
    try:
        f = date.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return str(texto or "")
    return f"{f.day} de {MESES[f.month - 1]} de {f.year}"


def _nombre_documento(tipo, numero_reporte=0):
    if tipo == "REPORTE_BIMESTRAL":
        return f"el reporte bimestral #{numero_reporte}"
    return "la " + TITULOS.get(tipo, tipo).split(" (")[0].lower()


def _datos_docx(con, alumno, servicio, tipo, numero_reporte=0, folio=""):
    programa = _datos_programa(con, servicio)
    requeridas = servicio["horas_requeridas"]
    acumuladas = horas_acumuladas(con, servicio["id"])
    return {
        "alumno_nombre": nombre_completo(alumno["nombre"], alumno["apellido_paterno"],
                                         alumno["apellido_materno"]),
        "nombre": alumno["nombre"],
        "apellido_paterno": alumno["apellido_paterno"],
        "apellido_materno": alumno["apellido_materno"],
        "control": alumno["identificador"],
        "curp": alumno["curp"],
        "carrera": alumno["carrera"],
        "semestre": alumno["semestre"],
        "plan": {"NUEVO": "Plan nuevo", "ANTIGUO": "Plan antiguo"}.get(
            alumno["plan_estudios"], "Por definir"),
        "programa": programa["programa"],
        "dependencia": programa["dependencia"],
        "responsable": programa["titular"],
        "domicilio": programa["domicilio"],
        "telefono": programa["telefono"],
        "periodo": programa["periodo"],
        "horas": programa["horas"],
        "horas_requeridas": requeridas,
        "horas_acumuladas": acumuladas,
        "actividades": programa["actividades"],
        "numero_reporte": numero_reporte or "",
        "folio": folio,
        "lugar_fecha": "Culiacán, Sinaloa, a " + date.today().strftime("%d/%m/%Y"),
    }


# --------------------------------------------------------------------- perfil
@alumno_bp.get("/api/alumno/perfil")
@login_requerido("ALUMNO")
def alumno_perfil():
    uid = session["usuario_id"]
    with transaccion() as con:
        a = _alumno(con, uid)
        if not a:
            return error("Expediente de alumno no encontrado", 404)
        s = _servicio_actual(con, uid)
        servicio = None
        if s:
            p = _datos_programa(con, s)
            avance = avance_horas(con, s)
            servicio = {
                "id": s["id"], "estatus": s["estatus"],
                "horas_requeridas": s["horas_requeridas"],
                "fecha_inicio": s["fecha_inicio"], "fecha_fin": s["fecha_fin"],
                "programa_id": p["id"], "programa_nombre": p["programa"],
                "empresa_nombre": p["dependencia"], "tipo": p["tipo"],
                "origen": p["origen"], "periodo": p["periodo"],
                **avance,
            }
        bloqueo = None if s else _bloqueo_solicitud(con, uid)
        no_leidas = con.execute(
            "SELECT COUNT(*) FROM notificaciones WHERE usuario_id = ? AND leida = 0",
            (uid,)).fetchone()[0]

    return jsonify({
        "nombre": a["nombre"],
        "apellido_paterno": a["apellido_paterno"],
        "apellido_materno": a["apellido_materno"],
        "nombre_completo": nombre_completo(a["nombre"], a["apellido_paterno"],
                                           a["apellido_materno"]),
        "identificador": a["identificador"],
        "correo": a["correo"],
        "curp": a["curp"],
        "carrera": a["carrera"],
        "semestre": a["semestre"],
        "plan_estudios": a["plan_estudios"],
        "creditos": a["creditos"],
        "porcentaje_creditos": a["porcentaje_creditos"],
        "telefono": a["telefono"] or "",
        "domicilio": a["domicilio"] or "",
        "servicio": servicio,
        "bloqueo": bloqueo,
        "notificaciones_no_leidas": no_leidas,
    })


@alumno_bp.patch("/api/alumno/perfil")
@login_requerido("ALUMNO")
def alumno_actualizar_perfil():
    datos = request.get_json(silent=True) or {}
    telefono = str(datos.get("telefono", "")).strip()
    domicilio = str(datos.get("domicilio", "")).strip()
    err = validar_telefono(telefono) if telefono else None
    if err:
        return error(err, 400)
    if not domicilio:
        return error("El domicilio es obligatorio", 400)
    if len(domicilio) > 200:
        return error("El domicilio no puede pasar de 200 caracteres", 400)

    with transaccion() as con:
        con.execute("UPDATE alumnos SET telefono = ?, domicilio = ?, "
                    "actualizado_en = datetime('now') WHERE usuario_id = ?",
                    (telefono or None, domicilio, session["usuario_id"]))
        registrar_bitacora(con, session["usuario_id"], "ACTUALIZAR_DATOS",
                           "Actualizó teléfono y domicilio")
    return jsonify({"ok": True, "mensaje": "Datos actualizados correctamente"})


# -------------------------------------------------------- banco / selección (CU06)
@alumno_bp.get("/api/programas/banco")
@login_requerido("ALUMNO")
def listar_banco_general():
    """Banco de propuestas: las del banco disponibles y las propuestas propias aprobadas."""
    uid = session["usuario_id"]
    with transaccion() as con:
        actual = _servicio_actual(con, uid)
        if actual and actual["estatus"] in ("CONCLUIDO", "LIBERADO"):
            return error("Ya concluyó su servicio social; el banco de propuestas ya no "
                         "está disponible.", 409)
        filas = con.execute(
            f"""SELECT p.id, p.tipo, p.origen, p.nombre, p.actividades, p.periodo,
                       p.horas, p.cupo, p.cupo_disponible, p.plan_estudios,
                       e.nombre AS empresa_nombre, {TITULAR_SQL} AS titular,
                       e.titular_nombre, e.titular_apellido_paterno,
                       e.titular_apellido_materno,
                       (SELECT {NOMBRE_SQL} FROM usuarios u WHERE u.id = p.propuesto_por)
                           AS propuesto_por_nombre
                FROM programas p JOIN empresas_receptoras e ON p.empresa_id = e.id
                WHERE (p.tipo = 'BANCO' AND p.estatus = 'DISPONIBLE')
                   OR (p.tipo = 'PROPIA' AND p.estatus = 'APROBADA')
                ORDER BY p.tipo DESC, p.nombre""").fetchall()
    return jsonify([dict(r) for r in filas])


@alumno_bp.get("/api/alumno/programas-disponibles")
@login_requerido("ALUMNO")
def alumno_programas_disponibles():
    uid = session["usuario_id"]
    with transaccion() as con:
        bloqueo = _bloqueo_solicitud(con, uid)
        if bloqueo:
            return jsonify([])
        plan = con.execute("SELECT plan_estudios FROM alumnos WHERE usuario_id = ?",
                           (uid,)).fetchone()["plan_estudios"]
        filas = con.execute(
            f"""SELECT p.id, p.tipo, p.origen, p.nombre, p.actividades, p.periodo,
                       p.cupo, p.cupo_disponible, e.nombre AS empresa_nombre,
                       {TITULAR_SQL} AS titular
                FROM programas p JOIN empresas_receptoras e ON p.empresa_id = e.id
                WHERE ((p.tipo = 'BANCO' AND p.estatus = 'DISPONIBLE')
                    OR (p.tipo = 'PROPIA' AND p.estatus = 'APROBADA'))
                  AND p.cupo_disponible > 0
                  AND p.plan_estudios IN ('AMBOS', ?)
                ORDER BY p.nombre""", (plan,)).fetchall()
    return jsonify([dict(r) for r in filas])


@alumno_bp.post("/api/alumno/seleccionar-programa")
@login_requerido("ALUMNO")
def alumno_seleccionar_programa():
    datos = request.get_json(silent=True) or {}
    try:
        programa_id = int(datos.get("programa_id"))
    except (TypeError, ValueError):
        return error("Debe seleccionar un programa", 400)
    uid = session["usuario_id"]

    with transaccion() as con:
        bloqueo = _bloqueo_solicitud(con, uid)
        if bloqueo:
            return error(bloqueo, 409)
        plan = con.execute("SELECT plan_estudios FROM alumnos WHERE usuario_id = ?",
                           (uid,)).fetchone()["plan_estudios"]
        prog = con.execute(
            "SELECT * FROM programas WHERE id = ? AND cupo_disponible > 0 "
            "AND ((tipo = 'BANCO' AND estatus = 'DISPONIBLE') "
            "  OR (tipo = 'PROPIA' AND estatus = 'APROBADA'))", (programa_id,)).fetchone()
        if not prog:
            return error("El programa seleccionado no está disponible", 409)
        if prog["plan_estudios"] not in ("AMBOS", plan):
            return error("El programa no es válido para su plan de estudios", 409)

        cur = con.execute(
            "UPDATE programas SET cupo_disponible = cupo_disponible - 1, "
            "actualizado_en = datetime('now') WHERE id = ? AND cupo_disponible > 0",
            (programa_id,))
        if cur.rowcount == 0:
            return error("El programa seleccionado ya no cuenta con cupo disponible", 409)

        servicio_id = con.execute(
            "INSERT INTO servicios_sociales (alumno_id, programa_id, estatus, horas_requeridas) "
            "VALUES (?, ?, 'PENDIENTE', ?)", (uid, programa_id, prog["horas"])).lastrowid
        notificar(con, uid, f"Su solicitud para el programa \"{prog['nombre']}\" fue registrada. "
                            "Queda pendiente de validación de la Oficina de Servicio Social.")
        notificar_rol(con, "JEFE_OFICINA_SS",
                      f"El alumno {session.get('nombre', uid)} solicitó el programa "
                      f"\"{prog['nombre']}\" (servicio {servicio_id}).")
        registrar_bitacora(con, uid, "SOLICITUD_SERVICIO",
                           f"Programa ID {programa_id}, servicio ID {servicio_id}")
    return jsonify({"ok": True, "servicio_id": servicio_id,
                    "mensaje": "Programa seleccionado correctamente"})


@alumno_bp.post("/api/alumno/propuesta-propia")
@login_requerido("ALUMNO")
def alumno_propuesta_propia():
    d = request.get_json(silent=True) or {}
    uid = session["usuario_id"]
    nombre = str(d.get("nombre", "")).strip()
    dependencia = str(d.get("dependencia", "")).strip()
    origen = str(d.get("origen", "")).strip().upper()
    periodo = str(d.get("periodo", "")).strip()
    actividades = str(d.get("actividades", "")).strip()
    domicilio = str(d.get("domicilio", "")).strip()
    telefono = str(d.get("telefono", "")).strip()
    objetivo = str(d.get("objetivo", "")).strip() or None
    area = str(d.get("area_responsable", "")).strip() or None

    # El responsable se captura con nombre y los dos apellidos.
    resp_nombre = str(d.get("responsable_nombre", "")).strip()
    resp_paterno = str(d.get("responsable_apellido_paterno", "")).strip()
    resp_materno = str(d.get("responsable_apellido_materno", "")).strip()
    if not (resp_nombre and resp_paterno and resp_materno):
        completo = str(d.get("responsable", "")).strip()
        partes = completo.split()
        if len(partes) >= 3:
            resp_nombre, resp_paterno, resp_materno = (
                " ".join(partes[:-2]), partes[-2], partes[-1])
        elif len(partes) == 2:
            resp_nombre, resp_paterno, resp_materno = partes[0], partes[1], ""

    err = (validar_nombres(resp_nombre, resp_paterno, resp_materno)
           or validar_origen(origen) or validar_periodo(periodo)
           or validar_telefono(telefono))
    if err:
        return error(err, 400)
    if not (nombre and dependencia and domicilio and actividades):
        return error("El nombre del programa, la dependencia, el domicilio y las "
                     "actividades son obligatorios", 400)
    if len(domicilio) > 200:
        return error("El domicilio no puede pasar de 200 caracteres", 400)

    with transaccion() as con:
        bloqueo = _bloqueo_solicitud(con, uid)
        if bloqueo:
            return error(bloqueo, 409)
        alumno = _alumno(con, uid)
        plan = alumno["plan_estudios"] or "AMBOS"
        titular = nombre_completo(resp_nombre, resp_paterno, resp_materno)

        # Cada propuesta guarda su propio responsable: nunca se reutiliza ni se
        # sobrescribe la fila de otra propuesta de la misma dependencia.
        empresa_id = con.execute(
            """INSERT INTO empresas_receptoras (nombre, titular_nombre,
                   titular_apellido_paterno, titular_apellido_materno, titular,
                   domicilio, telefono)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (dependencia, resp_nombre, resp_paterno, resp_materno, titular,
             domicilio, telefono)).lastrowid

        programa_id = con.execute(
            """INSERT INTO programas (tipo, origen, nombre, empresa_id, area_responsable,
                   objetivo, actividades, horas, cupo, cupo_disponible, periodo, plan_estudios,
                   estatus, propuesto_por)
               VALUES ('PROPIA', ?, ?, ?, ?, ?, ?, 480, 1, 0, ?, ?, 'PENDIENTE', ?)""",
            (origen, nombre, empresa_id, area, objetivo, actividades, periodo, plan,
             uid)).lastrowid
        servicio_id = con.execute(
            "INSERT INTO servicios_sociales (alumno_id, programa_id, estatus, horas_requeridas) "
            "VALUES (?, ?, 'PENDIENTE', 480)", (uid, programa_id)).lastrowid

        notificar(con, uid, f"Su propuesta propia \"{nombre}\" quedó pendiente de validación "
                            "por la Oficina de Servicio Social.")
        notificar_rol(con, "JEFE_OFICINA_SS",
                      f"El alumno {alumno['nombre']} {alumno['apellido_paterno']} "
                      f"{alumno['apellido_materno']} registró la propuesta propia "
                      f"\"{nombre}\" (programa {programa_id}).")
        registrar_bitacora(con, uid, "PROPUESTA_PROPIA",
                           f"Propuesta propia registrada: {nombre} (programa {programa_id})")
    return jsonify({"ok": True, "id": programa_id, "servicio_id": servicio_id,
                    "mensaje": "Propuesta propia enviada para revisión"})


@alumno_bp.get("/api/alumno/mis-propuestas")
@login_requerido("ALUMNO")
def alumno_mis_propuestas():
    """Propuestas propias del alumno con su dictamen (CU09, CU06)."""
    uid = session["usuario_id"]
    with transaccion() as con:
        filas = con.execute(
            """SELECT p.id, p.nombre, p.origen, p.actividades, p.periodo, p.horas,
                      p.estatus, p.motivo_rechazo, p.validado_en, p.creado_en,
                      e.nombre AS dependencia, e.titular, e.titular_nombre,
                      e.titular_apellido_paterno, e.titular_apellido_materno,
                      e.domicilio, e.telefono,
                      ss.id AS servicio_id, ss.estatus AS servicio_estatus
               FROM programas p
               JOIN empresas_receptoras e ON e.id = p.empresa_id
               LEFT JOIN servicios_sociales ss ON ss.programa_id = p.id
               WHERE p.tipo = 'PROPIA' AND p.propuesto_por = ?
               ORDER BY p.id DESC""", (uid,)).fetchall()
    return jsonify([dict(r) for r in filas])


# ------------------------------------------------------------------- horas (RF-08)
@alumno_bp.get("/api/alumno/avance-horas")
@login_requerido("ALUMNO")
def alumno_avance_horas():
    uid = session["usuario_id"]
    with transaccion() as con:
        s = _servicio_actual(con, uid)
        if not s:
            return error("No cuenta con un servicio social registrado", 404)
        p = _datos_programa(con, s)
        return jsonify({"servicio_id": s["id"], "programa": p["programa"],
                        "dependencia": p["dependencia"], "estatus": s["estatus"],
                        **avance_horas(con, s)})


# ------------------------------------------------------------ documentos (CU07)
@alumno_bp.get("/api/alumno/documentos")
@login_requerido("ALUMNO")
def alumno_listar_documentos():
    uid = session["usuario_id"]
    with transaccion() as con:
        s = _servicio_actual(con, uid)
        if not s:
            return jsonify([])
        plantillas = {f["tipo"] for f in con.execute("SELECT tipo FROM plantillas_documento")}
        resultado = []
        for tipo, num in documentos_requeridos(con, s["id"]):
            r = documento_vigente(con, s["id"], tipo, num)
            obs = None
            if r:
                o = con.execute("SELECT texto FROM observaciones WHERE documento_id = ? "
                                "ORDER BY id DESC LIMIT 1", (r["id"],)).fetchone()
                obs = o["texto"] if o else None
            periodo = estado_periodo(con, tipo, num)
            resultado.append({
                "tipo": tipo, "numero_reporte": num,
                "estatus": r["estatus"] if r else "SIN_SUBIR",
                "observaciones": obs,
                "documento_id": r["id"] if r else None,
                "version": r["version"] if r else None,
                "subido_en": r["subido_en"] if r else None,
                # Periodo de entrega definido por el Jefe de Oficina (RF-09).
                "fecha_inicio": periodo["fecha_inicio"],
                "fecha_fin": periodo["fecha_fin"],
                "abierto": periodo["abierto"],
                "motivo_bloqueo": periodo["motivo"],
                # La plantilla se puede descargar siempre, sin importar la fecha.
                "plantilla": tipo in plantillas,
            })

        # La carta de terminación la sube el Jefe de Vinculación en Word (editable);
        # el alumno la descarga, la firma y sube el PDF. Se habilita cuando el
        # expediente ya está validado (todos los documentos y las horas).
        carta = carta_terminacion(con, s["id"])                 # Word del Jefe
        habilitada = carta_terminacion_habilitada(con, s["id"])  # Word descargable
        firmada = carta_firmada_alumno(con, s["id"], uid)        # PDF del alumno
        resultado.append({
            "tipo": "CARTA_TERMINACION", "numero_reporte": 0,
            "estatus": ("VALIDADO" if firmada
                        else "PENDIENTE" if habilitada else "SIN_SUBIR"),
            "observaciones": None,
            "documento_id": firmada["id"] if firmada else None,
            "version": None,
            "subido_en": carta["subido_en"] if carta else None,
            "nombre_original": carta["nombre_original"] if carta else None,
            "fecha_inicio": None, "fecha_fin": None,
            "abierto": bool(habilitada),
            "motivo_bloqueo": None if habilitada else "DOCUMENTOS_PENDIENTES",
            "plantilla": False,
            # Word editable que subió Vinculación (solo descarga).
            "carta_word_id": habilitada["id"] if habilitada else None,
            "puede_descargar": bool(habilitada),
            # El alumno puede subir su PDF firmado cuando ya descargó el Word.
            "puede_subir": bool(habilitada) and not firmada,
            "firmada": bool(firmada),
            "documentos_pendientes": len(documentos_faltantes(con, s["id"])),
        })
    return jsonify(resultado)


@alumno_bp.post("/api/alumno/documentos")
@login_requerido("ALUMNO")
def alumno_subir_documento():
    uid = session["usuario_id"]
    tipo = request.form.get("tipo", "").strip().upper()
    try:
        numero_reporte = int(request.form.get("numero_reporte", 0))
    except (TypeError, ValueError):
        numero_reporte = 0

    if tipo not in TIPOS_DOCUMENTO:
        return error("Tipo de documento no válido", 400)
    if tipo == "REPORTE_BIMESTRAL" and numero_reporte not in (1, 2, 3):
        return error("Número de reporte no válido", 400)
    if tipo != "REPORTE_BIMESTRAL":
        numero_reporte = 0

    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        return error("No se adjuntó ningún archivo", 400)
    nombre_original = secure_filename(archivo.filename) or "documento.pdf"
    tamano = archivos.tamano(archivo)
    err = validar_pdf(nombre_original, tamano)
    if not err and not archivos.es_pdf(archivo):
        err = "Archivo no válido: no es un PDF"
    if err:
        return error(err, 400)
    archivo.stream.seek(0)

    with transaccion() as con:
        s = _servicio_actual(con, uid)
        if not s:
            return error("Primero debe seleccionar un programa de servicio social", 409)
        if s["estatus"] in ("BAJA", "LIBERADO"):
            return error("Su servicio social ya no permite subir documentos", 409)
        servicio_id = s["id"]

        externo = con.execute(
            "SELECT 1 FROM programas WHERE id = ? AND origen = 'EXTERNA'",
            (s["programa_id"],)).fetchone() is not None
        if tipo == "CARTA_PRESENTACION" and not externo:
            return error("La carta de presentación solo se requiere en servicios externos", 400)

        # RF-09: cada documento solo se puede subir dentro de su periodo global.
        # La carta de terminación es la excepción: se rige por la validación del
        # expediente y por la carta en Word que subió Vinculación.
        if tipo == "CARTA_TERMINACION":
            if not listo_para_carta(con, servicio_id):
                return error("La carta de terminación se habilita cuando todos sus "
                             "documentos estén validados y sus horas completas.", 409)
            if not carta_terminacion(con, servicio_id):
                return error("El Jefe de Vinculación aún no ha subido la carta en Word. "
                             "Intente de nuevo más tarde.", 409)
            if carta_firmada_alumno(con, servicio_id, uid):
                return error("Ya subió su carta de terminación firmada.", 409)
        else:
            periodo = estado_periodo(con, tipo, numero_reporte)
            if not periodo["abierto"]:
                nombre_doc = _nombre_documento(tipo, numero_reporte)
                if periodo["motivo"] == "SIN_PERIODO":
                    return error(f"La Oficina de Servicio Social todavía no ha definido el "
                                 f"periodo para subir {nombre_doc}", 409)
                if periodo["motivo"] == "NO_INICIADO":
                    return error(f"El periodo para subir {nombre_doc} inicia el "
                                 f"{_fecha_larga(periodo['fecha_inicio'])}", 409)
                return error(f"El periodo para subir {nombre_doc} venció el "
                             f"{_fecha_larga(periodo['fecha_fin'])}. Solicite a la Oficina de "
                             f"Servicio Social que lo reabra", 409)

            actual = documento_vigente(con, servicio_id, tipo, numero_reporte)
            if actual and actual["estatus"] == "VALIDADO":
                return error("Este documento ya fue validado", 409)

        version = (con.execute(
            "SELECT COALESCE(MAX(version), 0) FROM documentos "
            "WHERE servicio_id = ? AND tipo = ? AND numero_reporte = ?",
            (servicio_id, tipo, numero_reporte)).fetchone()[0] or 0) + 1
        guardado, relativa = archivos.guardar(archivo, f"alumnos/{uid}")

        # Solo se reemplazan las versiones del propio alumno: el Word que subió
        # Vinculación se conserva para que el alumno lo pueda volver a descargar.
        con.execute("UPDATE documentos SET estatus = 'REEMPLAZADO' WHERE servicio_id = ? "
                    "AND tipo = ? AND numero_reporte = ? AND subido_por = ? "
                    "AND estatus <> 'REEMPLAZADO'",
                    (servicio_id, tipo, numero_reporte, uid))
        if tipo == "CARTA_TERMINACION":
            # La carta firmada cierra el expediente: se registra como validada.
            con.execute(
                """INSERT INTO documentos (servicio_id, tipo, numero_reporte, version,
                       estatus, nombre_original, ruta_archivo, tamano_bytes, subido_por,
                       revisado_en)
                   VALUES (?, ?, ?, ?, 'VALIDADO', ?, ?, ?, ?, datetime('now'))""",
                (servicio_id, tipo, numero_reporte, version, nombre_original,
                 relativa, tamano, uid))
            con.execute(
                "UPDATE servicios_sociales SET estatus = 'LIBERADO', "
                "fecha_fin = COALESCE(fecha_fin, ?), actualizado_en = datetime('now') "
                "WHERE id = ?", (date.today().isoformat(), servicio_id))
            notificar(con, uid, "Su carta de terminación firmada fue recibida. "
                                "Su servicio social quedó LIBERADO.")
        else:
            con.execute(
                """INSERT INTO documentos (servicio_id, tipo, numero_reporte, version, estatus,
                       nombre_original, ruta_archivo, tamano_bytes, subido_por)
                   VALUES (?, ?, ?, ?, 'PENDIENTE', ?, ?, ?, ?)""",
                (servicio_id, tipo, numero_reporte, version, nombre_original,
                 relativa, tamano, uid))
        nombre_doc = TITULOS.get(tipo, tipo).split(" (")[0]
        if tipo == "REPORTE_BIMESTRAL":
            nombre_doc = f"Reporte bimestral #{numero_reporte}"
        notificar_rol(con, "JEFE_OFICINA_SS",
                      f"El alumno {session.get('nombre', uid)} subió {nombre_doc} "
                      f"(servicio {servicio_id}, versión {version}).")
        notificar_rol(con, "JEFE_VINCULACION",
                      f"El alumno {session.get('nombre', uid)} subió {nombre_doc} "
                      f"(servicio {servicio_id}, versión {version}).")
        registrar_bitacora(con, uid, "SUBIR_DOCUMENTO",
                           f"{tipo} #{numero_reporte} v{version} (servicio {servicio_id})")
    if tipo == "CARTA_TERMINACION":
        return jsonify({"ok": True, "liberado": True,
                        "mensaje": "Carta de terminación subida. Su servicio social "
                                   "quedó LIBERADO."})
    return jsonify({"ok": True, "mensaje": "Documento subido correctamente"})


# ------------------------------------- plantillas del Jefe (RF-06, sin fecha)
@alumno_bp.get("/api/alumno/plantillas/<tipo>/archivo")
@login_requerido("ALUMNO")
def alumno_descargar_plantilla(tipo):
    """Descarga la plantilla Word del documento para llenarla y subirla en PDF.

    La plantilla NO depende de las fechas: se puede descargar en cualquier
    momento. Si ya hay plantilla subida por el Jefe de Oficina, se entrega con
    los datos del alumno sustituidos; si no, se entrega tal cual.
    """
    tipo = tipo.upper()
    if tipo not in TIPOS_DOCUMENTO:
        return error("Tipo de documento no válido", 400)
    if tipo == "CARTA_TERMINACION":
        return error("La carta de terminación la sube el Jefe de Vinculación; "
                     "descárguela desde la sección de documentos.", 403)
    try:
        numero_reporte = int(request.args.get("numero_reporte", 0))
    except (TypeError, ValueError):
        numero_reporte = 0
    if tipo == "REPORTE_BIMESTRAL":
        if numero_reporte not in (1, 2, 3):
            return error("Indique el número de reporte (1 a 3)", 400)
    else:
        numero_reporte = 0

    uid = session["usuario_id"]
    with transaccion() as con:
        fila = con.execute(
            "SELECT nombre_original, ruta_archivo FROM plantillas_documento WHERE tipo = ?",
            (tipo,)).fetchone()
        if not fila:
            return error("La Oficina de Servicio Social todavía no ha subido la plantilla "
                         "de este documento", 404)
        ruta = archivos.ruta_segura(fila["ruta_archivo"])
        if not ruta or not ruta.is_file():
            return error("La plantilla de este documento no está disponible", 404)

        contenido = ruta.read_bytes()
        s = _servicio_actual(con, uid)
        if s:
            try:
                contenido = generar_docx(
                    tipo, _datos_docx(con, _alumno(con, uid), s, tipo, numero_reporte),
                    contenido)
            except Exception:
                pass   # si la plantilla no se puede procesar se entrega sin cambios
        registrar_bitacora(con, uid, "DESCARGAR_PLANTILLA",
                           f"{tipo} (archivo {fila['nombre_original']})")

    nombre = Path(fila["nombre_original"]).name or f"{tipo.lower()}.docx"
    return send_file(
        io.BytesIO(contenido), as_attachment=True, download_name=nombre,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# ------------------------------------------------------------ formatos Word (RF-06)
@alumno_bp.get("/api/alumno/formatos/<tipo>")
@login_requerido("ALUMNO")
def alumno_formato_word(tipo):
    tipo = tipo.upper()
    if tipo not in TITULOS or tipo == "CONSTANCIA":
        return error("Tipo de documento no válido", 400)
    if tipo == "CARTA_TERMINACION":
        return error("La carta de terminación la emite el Jefe de Vinculación en Word; "
                     "usted solo puede descargarla.", 403)
    try:
        numero_reporte = int(request.args.get("numero_reporte", 0))
    except ValueError:
        numero_reporte = 0
    uid = session["usuario_id"]

    with transaccion() as con:
        alumno = _alumno(con, uid)
        s = _servicio_actual(con, uid)
        if not s:
            return error("Debe tener un programa de servicio social seleccionado", 409)
        if tipo == "REPORTE_BIMESTRAL" and numero_reporte not in (1, 2, 3):
            return error("Indique el número de reporte (1 a 3)", 400)
        datos = _datos_docx(con, alumno, s, tipo, numero_reporte)
        plantilla = con.execute("SELECT ruta_archivo FROM plantillas_documento WHERE tipo = ?",
                                (tipo,)).fetchone()
        contenido_plantilla = None
        if plantilla:
            ruta = archivos.ruta_segura(plantilla["ruta_archivo"])
            if ruta and ruta.is_file():
                contenido_plantilla = ruta.read_bytes()
        try:
            contenido = generar_docx(tipo, datos, contenido_plantilla)
        except Exception:
            return error("No fue posible generar el documento Word", 500)

        con.execute("INSERT INTO expediciones (servicio_id, tipo, generada_por) VALUES (?, ?, ?)",
                    (s["id"], tipo, uid))
        registrar_bitacora(con, uid, "EXPEDIR_DOCUMENTO", f"{tipo} (servicio {s['id']})")
    nombre = f"{tipo.lower()}"
    if tipo == "REPORTE_BIMESTRAL":
        nombre += f"_{numero_reporte}"
    return send_file(io.BytesIO(contenido), as_attachment=True,
                     download_name=f"{nombre}.docx",
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# -------------------------------------------------------- inducción (CU03)
@alumno_bp.get("/api/alumno/induccion")
@login_requerido("ALUMNO")
def alumno_induccion():
    uid = session["usuario_id"]
    with transaccion() as con:
        curso = con.execute("SELECT * FROM cursos_induccion WHERE activo = 1 "
                            "ORDER BY fecha DESC, id DESC LIMIT 1").fetchone()
        if not curso:
            return jsonify({"disponible": False,
                            "mensaje": "No hay curso de inducción programado"})
        asistencia = con.execute(
            "SELECT * FROM asistencias_induccion WHERE curso_id = ? AND alumno_id = ?",
            (curso["id"], uid)).fetchone()
        forms = con.execute(
            "SELECT enviado_en FROM forms_induccion WHERE curso_id = ? AND alumno_id = ?",
            (curso["id"], uid)).fetchone()
    return jsonify({
        "disponible": True,
        "curso": {"id": curso["id"], "fecha": curso["fecha"], "lugar": curso["lugar"],
                  "periodo": curso["periodo"]},
        "asistencia_registrada": bool(asistencia),
        "forms_completos": bool(asistencia and asistencia["forms_completos"]),
        "forms_enviado_en": forms["enviado_en"] if forms else None,
        "qr_vigente": bool(curso["qr_token"] and curso["qr_expira_en"]
                           and curso["qr_expira_en"] >= datetime.now(timezone.utc)
                           .strftime("%Y-%m-%d %H:%M:%S")),
    })


@alumno_bp.post("/api/alumno/induccion/qr")
@login_requerido("ALUMNO")
def alumno_induccion_qr():
    token = str((request.get_json(silent=True) or {}).get("token", "")).strip()
    if not token:
        return error("Escanee el código QR del curso", 400)
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    uid = session["usuario_id"]
    with transaccion() as con:
        curso = con.execute(
            "SELECT * FROM cursos_induccion WHERE qr_token = ? AND activo = 1 "
            "AND qr_expira_en >= ?", (token, ahora)).fetchone()
        if not curso:
            return error("El código QR es inválido o expiró. Solicite uno nuevo.", 409)
        con.execute("INSERT INTO asistencias_induccion (curso_id, alumno_id, forms_completos) "
                    "VALUES (?, ?, 0) ON CONFLICT(curso_id, alumno_id) DO NOTHING",
                    (curso["id"], uid))
        registrar_bitacora(con, uid, "ASISTENCIA_INDUCCION", f"Curso {curso['id']}")
    return jsonify({"ok": True, "mensaje": "Asistencia registrada correctamente",
                    "curso_id": curso["id"]})


@alumno_bp.post("/api/alumno/induccion/forms")
@login_requerido("ALUMNO")
def alumno_induccion_forms():
    respuestas = (request.get_json(silent=True) or {}).get("respuestas")
    if not respuestas or not isinstance(respuestas, (dict, list)):
        return error("Debe completar los FORMS", 400)
    import json
    uid = session["usuario_id"]
    with transaccion() as con:
        curso = con.execute("SELECT * FROM cursos_induccion WHERE activo = 1 "
                            "ORDER BY fecha DESC, id DESC LIMIT 1").fetchone()
        if not curso:
            return error("No hay curso de inducción programado", 409)
        asistencia = con.execute(
            "SELECT * FROM asistencias_induccion WHERE curso_id = ? AND alumno_id = ?",
            (curso["id"], uid)).fetchone()
        if not asistencia:
            return error("Primero debe registrar su asistencia escaneando el código QR", 409)
        con.execute(
            "INSERT INTO forms_induccion (curso_id, alumno_id, respuestas) VALUES (?, ?, ?) "
            "ON CONFLICT(curso_id, alumno_id) DO UPDATE SET respuestas = excluded.respuestas, "
            "enviado_en = datetime('now')",
            (curso["id"], uid, json.dumps(respuestas, ensure_ascii=False)))
        con.execute("UPDATE asistencias_induccion SET forms_completos = 1 "
                    "WHERE curso_id = ? AND alumno_id = ?", (curso["id"], uid))
        registrar_bitacora(con, uid, "FORMS_INDUCCION", f"Curso {curso['id']}")
    return jsonify({"ok": True, "mensaje": "Curso de inducción registrado correctamente"})


# ---------------------------------------------------------- baja del alumno (RF-16)
@alumno_bp.post("/api/alumno/baja")
@login_requerido("ALUMNO")
def alumno_baja_servicio():
    motivo = str((request.get_json(silent=True) or {}).get("motivo", "")).strip()
    if not motivo:
        return error("Indique el motivo de la baja", 400)
    uid = session["usuario_id"]
    with transaccion() as con:
        s = _servicio_actual(con, uid)
        if not s:
            return error("No cuenta con un servicio social registrado", 404)
        if s["estatus"] not in ("PENDIENTE", "ACTIVO"):
            return error("Solo se puede dar de baja un servicio activo o pendiente", 409)
        con.execute("INSERT INTO bajas (servicio_id, motivo, registrada_por) VALUES (?, ?, ?)",
                    (s["id"], motivo, uid))
        con.execute("UPDATE servicios_sociales SET estatus = 'BAJA', "
                    "actualizado_en = datetime('now') WHERE id = ?", (s["id"],))
        liberar_cupo(con, s["programa_id"])
        notificar(con, uid, f"Su servicio social fue dado de baja. Motivo: {motivo}")
        notificar_rol(con, "JEFE_OFICINA_SS",
                      f"El alumno {session.get('nombre', uid)} dio de baja su servicio "
                      f"{s['id']}. Motivo: {motivo}")
        registrar_bitacora(con, uid, "BAJA_SERVICIO", f"Servicio {s['id']}: {motivo}")
    return jsonify({"ok": True, "mensaje": "Servicio social dado de baja"})


# ------------------------------------------------------------ notificaciones
@alumno_bp.get("/api/notificaciones")
@login_requerido()
def listar_notificaciones():
    with transaccion() as con:
        filas = con.execute(
            "SELECT id, mensaje, leida, creada_en FROM notificaciones "
            "WHERE usuario_id = ? ORDER BY id DESC LIMIT 50",
            (session["usuario_id"],)).fetchall()
    return jsonify([dict(r) for r in filas])


@alumno_bp.post("/api/notificaciones/leer")
@login_requerido()
def leer_notificaciones():
    with transaccion() as con:
        con.execute("UPDATE notificaciones SET leida = 1 WHERE usuario_id = ?",
                    (session["usuario_id"],))
    return jsonify({"ok": True})
