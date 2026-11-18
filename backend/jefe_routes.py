"""Rutas del Jefe de Oficina de Servicio Social.

Cubre CU08 (banco de propuestas), CU09 (propuestas propias), CU10 (validar
documentos), CU11 (reportes bimestrales faltantes), RF-06 (plantillas Word),
RF-12 (editar programas), RF-13 (planes), RF-14 (periodo oficial), RF-16 (bajas)
y RF-17 (validar el programa contra el plan del alumno).
"""
from __future__ import annotations

import uuid
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, session

from backend.comun import (
    NOMBRE_SQL, avance_horas, documentos_faltantes, horas_acumuladas,
    liberar_cupo, notificar, notificar_rol, quizas_concluir,
)
from backend.db import conectar, registrar_bitacora, transaccion
from backend.rutas import archivos
from backend.seguridad import error, login_requerido
from backend.validaciones import (
    validar_fecha, validar_nombres, validar_origen, validar_periodo, validar_plan,
    validar_telefono,
)

jefe_bp = Blueprint("jefe_bp", __name__)

JEFE = "JEFE_OFICINA_SS"
MAX_BYTES_PLANTILLA = 5 * 1024 * 1024
PLANES = ("NUEVO", "ANTIGUO", "AMBOS")
ESTADOS_PROGRAMA_BANCO = ("DISPONIBLE", "INACTIVO")

TIPOS_PLANTILLA = {
    "CARTA_PRESENTACION": "Carta de presentación (solo servicio externo)",
    "SOLICITUD": "Solicitud de servicio social",
    "CARTA_ACEPTACION": "Carta de aceptación",
    "REPORTE_BIMESTRAL": "Reporte bimestral (sirve para los 3 reportes)",
    "MEMORIA_FINAL": "Memoria final",
    "CARTA_TERMINACION": "Carta de terminación",
}

COLUMNAS_PROGRAMA = """p.id, p.tipo, p.origen, p.nombre, p.area_responsable, p.objetivo,
       p.actividades, p.horas, p.cupo, p.cupo_disponible, p.periodo, p.plan_estudios,
       p.estatus, p.creado_en, p.validado_en,
       e.nombre AS empresa_nombre, e.titular, e.titular_nombre,
       e.titular_apellido_paterno, e.titular_apellido_materno,
       e.domicilio, e.telefono"""


# ------------------------------------------------------------------ utilidades
def _datos():
    return request.get_json(silent=True) or {}


def _entero(valor, defecto=None, minimo=1, maximo=None):
    if valor in (None, ""):
        return defecto
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    if numero < minimo:
        return None
    if maximo is not None and numero > maximo:
        return None
    return numero


def _nombres_titular(datos):
    """Devuelve (nombre, paterno, materno) del responsable.

    El formulario nuevo manda los tres campos. Para no romper clientes viejos se
    acepta también ``titular`` completo, pero solo si trae los dos apellidos.
    """
    nombre = str(datos.get("titular_nombre", "")).strip()
    paterno = str(datos.get("titular_apellido_paterno", "")).strip()
    materno = str(datos.get("titular_apellido_materno", "")).strip()
    if nombre and paterno and materno:
        return nombre, paterno, materno

    completo = str(datos.get("titular", "")).strip()
    partes = completo.split()
    if len(partes) >= 4:
        return " ".join(partes[:-2]), partes[-2], partes[-1]
    if len(partes) == 3:
        return partes[0], partes[1], partes[2]
    return nombre, paterno, materno


def _titular_completo(nombre, paterno, materno):
    return " ".join(p for p in (nombre, paterno, materno) if p).strip()


def _ocupados(con, programa_id):
    return con.execute(
        "SELECT COUNT(*) FROM servicios_sociales WHERE programa_id = ? AND estatus <> 'BAJA'",
        (programa_id,)).fetchone()[0]


def _servicio(con, servicio_id):
    return con.execute("SELECT * FROM servicios_sociales WHERE id = ?",
                       (servicio_id,)).fetchone()


def _nombre_documento(tipo, numero_reporte=0):
    if tipo == "REPORTE_BIMESTRAL":
        return f"Reporte bimestral #{numero_reporte}"
    return TIPOS_PLANTILLA.get(tipo, tipo).split(" (")[0]


# ============================================================ Plantillas en Word
@jefe_bp.get("/api/jefe/plantillas")
@login_requerido(JEFE)
def jefe_listar_plantillas():
    with closing(conectar()) as con:
        subidas = {r["tipo"]: r for r in con.execute(
            "SELECT tipo, nombre_original, subido_en FROM plantillas_documento")}
    return jsonify([{
        "tipo": tipo,
        "titulo": titulo,
        "nombre_archivo": subidas[tipo]["nombre_original"] if tipo in subidas else None,
        "subido_en": subidas[tipo]["subido_en"] if tipo in subidas else None,
    } for tipo, titulo in TIPOS_PLANTILLA.items()])


@jefe_bp.post("/api/jefe/plantillas")
@login_requerido(JEFE)
def jefe_subir_plantilla():
    tipo = request.form.get("tipo", "").strip().upper()
    archivo = request.files.get("archivo")
    if tipo not in TIPOS_PLANTILLA:
        return error("Seleccione el documento al que pertenece la plantilla", 400)
    if not archivo or not archivo.filename:
        return error("No se adjuntó ningún archivo", 400)

    nombre_original = Path(archivo.filename).name[:150] or "plantilla.docx"
    if not nombre_original.lower().endswith(".docx"):
        return error("Archivo no válido: la plantilla debe ser un Word (.docx)", 400)
    tamano = archivos.tamano(archivo)
    if tamano <= 0 or tamano > MAX_BYTES_PLANTILLA:
        return error("Archivo no válido: está vacío o excede 5 MB", 400)
    if archivo.stream.read(4) != b"PK\x03\x04":   # un .docx es un zip
        return error("Archivo no válido: no es un documento de Word (.docx)", 400)
    archivo.stream.seek(0)

    guardado = None
    anterior = None
    try:
        with transaccion() as con:
            anterior = con.execute(
                "SELECT ruta_archivo FROM plantillas_documento WHERE tipo = ?",
                (tipo,)).fetchone()
            guardado, relativa = archivos.guardar(archivo, "plantillas", ".docx")
            con.execute(
                """INSERT INTO plantillas_documento
                       (tipo, nombre_original, ruta_archivo, subido_por)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(tipo) DO UPDATE SET
                       nombre_original = excluded.nombre_original,
                       ruta_archivo = excluded.ruta_archivo,
                       subido_por = excluded.subido_por,
                       subido_en = datetime('now')""",
                (tipo, nombre_original, relativa, session["usuario_id"]))
            registrar_bitacora(con, session["usuario_id"], "SUBIR_PLANTILLA",
                               f"Plantilla: {tipo}")
    except Exception:
        if guardado:
            guardado.unlink(missing_ok=True)
        raise

    if anterior:
        vieja = archivos.ruta_segura(anterior["ruta_archivo"])
        if vieja:
            vieja.unlink(missing_ok=True)
    return jsonify({"ok": True, "mensaje": "Plantilla guardada correctamente"})


@jefe_bp.get("/api/jefe/plantillas/<tipo>/archivo")
@login_requerido(JEFE)
def jefe_descargar_plantilla(tipo):
    tipo = tipo.upper()
    if tipo not in TIPOS_PLANTILLA:
        return error("Tipo de documento no válido", 400)
    with closing(conectar()) as con:
        fila = con.execute(
            "SELECT nombre_original, ruta_archivo FROM plantillas_documento WHERE tipo = ?",
            (tipo,)).fetchone()
    ruta = archivos.ruta_segura(fila["ruta_archivo"]) if fila else None
    if not ruta or not ruta.is_file():
        return error("Todavía no hay una plantilla disponible para este documento", 404)
    return send_file(
        ruta, as_attachment=True, download_name=fila["nombre_original"],
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# ====================================================== Banco de propuestas (CU08)
@jefe_bp.get("/api/jefe/programas")
@login_requerido(JEFE)
def jefe_listar_programas():
    """Propuestas del banco (visibles u ocultas) y propias aprobadas."""
    with closing(conectar()) as con:
        filas = con.execute(
            f"""SELECT {COLUMNAS_PROGRAMA}, {NOMBRE_SQL} AS propuesto_por_nombre
                FROM programas p
                JOIN empresas_receptoras e ON p.empresa_id = e.id
                LEFT JOIN usuarios u ON p.propuesto_por = u.id
                WHERE p.tipo = 'BANCO' OR (p.tipo = 'PROPIA' AND p.estatus = 'APROBADA')
                ORDER BY p.id DESC""").fetchall()
    return jsonify([dict(r) for r in filas])


@jefe_bp.post("/api/jefe/programas")
@login_requerido(JEFE)
def jefe_crear_programa():
    d = _datos()
    campo = lambda k: str(d.get(k, "")).strip()
    nombre, empresa = campo("nombre"), campo("empresa")
    domicilio, telefono = campo("domicilio"), campo("telefono")
    actividades, periodo = campo("actividades"), campo("periodo")
    area, objetivo = campo("area_responsable") or None, campo("objetivo") or None
    origen = campo("origen").upper()
    plan = campo("plan_estudios").upper() or "AMBOS"
    horas = _entero(d.get("horas"), 480)
    cupo = _entero(d.get("cupo"))

    resp_nombre, resp_paterno, resp_materno = _nombres_titular(d)
    err = (validar_nombres(resp_nombre, resp_paterno, resp_materno)
           or validar_telefono(telefono) or validar_origen(origen)
           or validar_periodo(periodo) or validar_plan(plan))
    if err:
        return error(err, 400)
    if not (nombre and empresa and domicilio and actividades):
        return error("Nombre del programa, empresa, domicilio y actividades son obligatorios", 400)
    if len(domicilio) > 200:
        return error("El domicilio no puede pasar de 200 caracteres", 400)
    if horas is None:
        return error("Las horas deben ser un número entero mayor que 0", 400)
    if cupo is None:
        return error("Los lugares disponibles deben ser un número entero mayor que 0", 400)

    titular = _titular_completo(resp_nombre, resp_paterno, resp_materno)
    with transaccion() as con:
        if con.execute(
                """SELECT 1 FROM programas p JOIN empresas_receptoras e ON e.id = p.empresa_id
                   WHERE p.tipo = 'BANCO' AND p.nombre = ? AND e.nombre = ?
                     AND p.periodo = ?""", (nombre, empresa, periodo)).fetchone():
            return error("Ya existe esa propuesta en el banco para el mismo periodo", 409)

        # Cada propuesta guarda su propio responsable: no se reutiliza la fila de
        # otra propuesta de la misma dependencia (eso sobrescribía el nombre).
        empresa_id = con.execute(
            """INSERT INTO empresas_receptoras
                   (nombre, titular_nombre, titular_apellido_paterno,
                    titular_apellido_materno, titular, domicilio, telefono)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (empresa, resp_nombre, resp_paterno, resp_materno, titular,
             domicilio, telefono)).lastrowid

        programa_id = con.execute(
            """INSERT INTO programas
                   (tipo, origen, nombre, empresa_id, area_responsable, objetivo,
                    actividades, horas, cupo, cupo_disponible, periodo, plan_estudios,
                    estatus, creado_por)
               VALUES ('BANCO', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DISPONIBLE', ?)""",
            (origen, nombre, empresa_id, area, objetivo, actividades, horas, cupo, cupo,
             periodo, plan, session["usuario_id"])).lastrowid
        registrar_bitacora(con, session["usuario_id"], "ALTA_PROGRAMA",
                           f"Programa ID {programa_id}: {nombre}")
        notificar_rol(con, "ALUMNO", f"Se publicó un nuevo programa en el banco: {nombre}")
    return jsonify({"ok": True, "id": programa_id, "mensaje": "Propuesta agregada al banco"})


@jefe_bp.patch("/api/jefe/programas/<int:programa_id>")
@login_requerido(JEFE)
def jefe_editar_programa(programa_id):
    """RF-12: editar nombre, objetivo, actividades, horas, cupo y estatus."""
    d = _datos()
    with transaccion() as con:
        p = con.execute("SELECT * FROM programas WHERE id = ?", (programa_id,)).fetchone()
        if not p:
            return error("Programa no encontrado", 404)
        if p["tipo"] != "BANCO":
            return error("Las propuestas propias se modifican desde su validación", 400)

        nombre = str(d.get("nombre", p["nombre"])).strip()
        actividades = str(d.get("actividades", p["actividades"])).strip()
        objetivo = str(d.get("objetivo", p["objetivo"] or "")).strip() or None
        area = str(d.get("area_responsable", p["area_responsable"] or "")).strip() or None
        periodo = str(d.get("periodo", p["periodo"])).strip()
        plan = str(d.get("plan_estudios", p["plan_estudios"])).strip().upper()
        estatus = str(d.get("estatus", p["estatus"])).strip().upper()
        horas = _entero(d.get("horas"), p["horas"])
        cupo = _entero(d.get("cupo"), p["cupo"])

        if not nombre or not actividades:
            return error("El nombre y las actividades son obligatorios", 400)
        if horas is None:
            return error("Las horas deben ser un número entero mayor que 0", 400)
        if cupo is None:
            return error("El cupo debe ser un número entero mayor que 0", 400)
        if plan not in PLANES:
            return error("Plan de estudios no válido", 400)
        if estatus not in ESTADOS_PROGRAMA_BANCO:
            return error("Estatus no válido", 400)
        if err := validar_periodo(periodo):
            return error(err, 400)

        ocupados = _ocupados(con, programa_id)
        if cupo < ocupados:
            return error(f"El cupo no puede ser menor que los alumnos ya asignados ({ocupados})", 409)
        if horas != p["horas"] and ocupados and not d.get("confirmar_horas"):
            return error("Hay alumnos asignados. Envíe confirmar_horas=true para cambiar las horas", 409)

        con.execute(
            """UPDATE programas SET nombre = ?, objetivo = ?, actividades = ?, horas = ?,
                      cupo = ?, cupo_disponible = ?, periodo = ?, plan_estudios = ?,
                      area_responsable = ?, estatus = ?, actualizado_en = datetime('now')
               WHERE id = ?""",
            (nombre, objetivo, actividades, horas, cupo, max(0, cupo - ocupados), periodo,
             plan, area, estatus, programa_id))
        registrar_bitacora(con, session["usuario_id"], "EDITAR_PROGRAMA",
                           f"Programa ID {programa_id}: {nombre}")
    return jsonify({"ok": True, "mensaje": "Programa actualizado correctamente",
                    "alumnos_asignados": ocupados})


@jefe_bp.patch("/api/jefe/programas/<int:programa_id>/estatus")
@login_requerido(JEFE)
def jefe_estatus_programa(programa_id):
    """Oculta (INACTIVO) o vuelve a publicar (DISPONIBLE) una propuesta del banco."""
    estatus = str(_datos().get("estatus", "")).strip().upper()
    if estatus not in ESTADOS_PROGRAMA_BANCO:
        return error("Estatus no válido", 400)
    with transaccion() as con:
        cur = con.execute(
            "UPDATE programas SET estatus = ?, actualizado_en = datetime('now') "
            "WHERE id = ? AND tipo = 'BANCO'", (estatus, programa_id))
        if cur.rowcount == 0:
            return error("Propuesta del banco no encontrada", 404)
        registrar_bitacora(con, session["usuario_id"], "ESTATUS_PROGRAMA",
                           f"Programa ID {programa_id}: {estatus}")
    return jsonify({"ok": True, "mensaje": "Estatus del programa actualizado"})


@jefe_bp.patch("/api/jefe/programas/<int:programa_id>/responsable")
@login_requerido(JEFE)
def jefe_editar_responsable(programa_id):
    """Corrige la dependencia y el responsable de UNA propuesta.

    Si la fila de empresa estaba compartida por varias propuestas (datos viejos),
    se separa una copia para que el cambio no afecte a las demás.
    """
    d = _datos()
    with transaccion() as con:
        p = con.execute("SELECT * FROM programas WHERE id = ?", (programa_id,)).fetchone()
        if not p:
            return error("Propuesta no encontrada", 404)
        emp = con.execute("SELECT * FROM empresas_receptoras WHERE id = ?",
                          (p["empresa_id"],)).fetchone()
        if not emp:
            return error("No se encontró la dependencia de la propuesta", 404)

        empresa = str(d.get("empresa", emp["nombre"]) or "").strip()
        domicilio = str(d.get("domicilio", emp["domicilio"]) or "").strip()
        telefono = str(d.get("telefono", emp["telefono"]) or "").strip()
        resp_nombre, resp_paterno, resp_materno = _nombres_titular({
            "titular_nombre": d.get("titular_nombre", emp["titular_nombre"]),
            "titular_apellido_paterno": d.get(
                "titular_apellido_paterno", emp["titular_apellido_paterno"]),
            "titular_apellido_materno": d.get(
                "titular_apellido_materno", emp["titular_apellido_materno"]),
        })

        err = (validar_nombres(resp_nombre, resp_paterno, resp_materno)
               or validar_telefono(telefono))
        if err:
            return error(err, 400)
        if not empresa or not domicilio:
            return error("La dependencia y el domicilio son obligatorios", 400)
        if len(domicilio) > 200:
            return error("El domicilio no puede pasar de 200 caracteres", 400)

        titular = _titular_completo(resp_nombre, resp_paterno, resp_materno)
        compartida = con.execute(
            "SELECT 1 FROM programas WHERE empresa_id = ? AND id <> ? LIMIT 1",
            (emp["id"], programa_id)).fetchone()
        if compartida:
            nuevo_id = con.execute(
                """INSERT INTO empresas_receptoras
                       (nombre, titular_nombre, titular_apellido_paterno,
                        titular_apellido_materno, titular, domicilio, telefono)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (empresa, resp_nombre, resp_paterno, resp_materno, titular,
                 domicilio, telefono)).lastrowid
            con.execute("UPDATE programas SET empresa_id = ?, actualizado_en = datetime('now') "
                        "WHERE id = ?", (nuevo_id, programa_id))
        else:
            con.execute(
                """UPDATE empresas_receptoras SET nombre = ?, titular_nombre = ?,
                       titular_apellido_paterno = ?, titular_apellido_materno = ?,
                       titular = ?, domicilio = ?, telefono = ?,
                       actualizado_en = datetime('now') WHERE id = ?""",
                (empresa, resp_nombre, resp_paterno, resp_materno, titular,
                 domicilio, telefono, emp["id"]))
        registrar_bitacora(con, session["usuario_id"], "EDITAR_RESPONSABLE",
                           f"Programa ID {programa_id}: {titular}")
    return jsonify({"ok": True, "mensaje": "Responsable actualizado correctamente"})


# ============================================== Propuestas propias de alumnos (CU09)
@jefe_bp.get("/api/jefe/propuestas-propias")
@login_requerido(JEFE)
def jefe_listar_propuestas_propias():
    estatus = request.args.get("estatus", "PENDIENTE").strip().upper()
    where, params = "p.tipo = 'PROPIA'", []
    if estatus in ("PENDIENTE", "APROBADA", "RECHAZADA"):
        where += " AND p.estatus = ?"
        params.append(estatus)
    elif estatus not in ("", "TODAS", "TODOS"):
        return error("Estatus no válido", 400)

    with closing(conectar()) as con:
        filas = con.execute(
            f"""SELECT {COLUMNAS_PROGRAMA}, p.motivo_rechazo, p.validado_en,
                       {NOMBRE_SQL} AS alumno_nombre, u.identificador AS alumno_control,
                       a.carrera AS alumno_carrera, a.plan_estudios AS alumno_plan
                FROM programas p
                JOIN empresas_receptoras e ON p.empresa_id = e.id
                JOIN usuarios u ON p.propuesto_por = u.id
                JOIN alumnos a ON a.usuario_id = u.id
                WHERE {where} ORDER BY p.id DESC""", params).fetchall()
    return jsonify([dict(r) for r in filas])


@jefe_bp.post("/api/jefe/propuestas-propias/<int:programa_id>/validar")
@login_requerido(JEFE)
def jefe_validar_propuesta_propia(programa_id):
    """Aprueba (y la publica en el banco) o rechaza (con motivo) una propuesta propia."""
    d = _datos()
    aprobar = d.get("aprobar") is True
    motivo = str(d.get("motivo", "")).strip()
    if not aprobar and not motivo:
        return error("Indique el motivo del rechazo para que el alumno lo conozca", 400)
    if len(motivo) > 2000:
        return error("El motivo no puede pasar de 2000 caracteres", 400)

    with transaccion() as con:
        p = con.execute("SELECT * FROM programas WHERE id = ? AND tipo = 'PROPIA'",
                        (programa_id,)).fetchone()
        if not p:
            return error("Propuesta no encontrada", 404)
        if p["estatus"] != "PENDIENTE":
            return error("Esta propuesta ya fue validada", 409)
        alumno_id = p["propuesto_por"]
        servicios = con.execute(
            "SELECT * FROM servicios_sociales WHERE programa_id = ? AND alumno_id = ? "
            "AND estatus <> 'BAJA'", (programa_id, alumno_id)).fetchall()

        if not aprobar:
            con.execute(
                "UPDATE programas SET estatus = 'RECHAZADA', motivo_rechazo = ?, "
                "cupo_disponible = 0, validado_por = ?, validado_en = datetime('now'), "
                "actualizado_en = datetime('now') WHERE id = ?",
                (motivo, session["usuario_id"], programa_id))
            for s in servicios:
                con.execute("UPDATE servicios_sociales SET estatus = 'BAJA', "
                            "actualizado_en = datetime('now') WHERE id = ?", (s["id"],))
                if not con.execute("SELECT 1 FROM bajas WHERE servicio_id = ?",
                                   (s["id"],)).fetchone():
                    con.execute(
                        "INSERT INTO bajas (servicio_id, motivo, registrada_por) VALUES (?, ?, ?)",
                        (s["id"], f"Propuesta propia rechazada: {motivo}",
                         session["usuario_id"]))
            liberar_cupo(con, programa_id)
            notificar(con, alumno_id,
                      f"Su propuesta propia \"{p['nombre']}\" fue rechazada: {motivo}. "
                      "Ya puede elegir otro programa.")
            registrar_bitacora(con, session["usuario_id"], "RECHAZAR_PROPUESTA",
                               f"Programa ID {programa_id}: {motivo}")
            return jsonify({"ok": True, "mensaje": "Propuesta rechazada; el alumno puede elegir otro programa"})

        cupo = _entero(d.get("cupo"), 1)
        horas = _entero(d.get("horas"), p["horas"])
        plan = str(d.get("plan_estudios") or "AMBOS").strip().upper()
        if cupo is None:
            return error("Los lugares disponibles deben ser un número entero mayor que 0", 400)
        if horas is None:
            return error("Las horas deben ser un número entero mayor que 0", 400)
        if plan not in PLANES:
            return error("Plan de estudios no válido", 400)

        ocupados = _ocupados(con, programa_id)
        if cupo < ocupados:
            return error(f"Los lugares no pueden ser menos que los ya ocupados ({ocupados})", 409)

        domicilio = str(d.get("domicilio", "")).strip()
        telefono = str(d.get("telefono", "")).strip()
        if domicilio or telefono:
            emp = con.execute("SELECT * FROM empresas_receptoras WHERE id = ?",
                              (p["empresa_id"],)).fetchone()
            nuevo_dom = domicilio or emp["domicilio"]
            nuevo_tel = telefono or emp["telefono"]
            if err := validar_telefono(nuevo_tel):
                return error(err, 400)
            compartida = con.execute(
                "SELECT 1 FROM programas WHERE empresa_id = ? AND id <> ? LIMIT 1",
                (emp["id"], programa_id)).fetchone()
            if compartida:
                # Fila compartida por datos viejos: se separa para no cambiar el
                # contacto de las demás propuestas.
                nuevo_id = con.execute(
                    """INSERT INTO empresas_receptoras
                           (nombre, titular_nombre, titular_apellido_paterno,
                            titular_apellido_materno, titular, domicilio, telefono)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (emp["nombre"], emp["titular_nombre"], emp["titular_apellido_paterno"],
                     emp["titular_apellido_materno"], emp["titular"], nuevo_dom,
                     nuevo_tel)).lastrowid
                con.execute("UPDATE programas SET empresa_id = ? WHERE id = ?",
                            (nuevo_id, programa_id))
            else:
                con.execute(
                    "UPDATE empresas_receptoras SET domicilio = ?, telefono = ?, "
                    "actualizado_en = datetime('now') WHERE id = ?",
                    (nuevo_dom, nuevo_tel, emp["id"]))

        con.execute(
            """UPDATE programas SET estatus = 'APROBADA', cupo = ?, cupo_disponible = ?,
                      horas = ?, plan_estudios = ?, area_responsable = ?, objetivo = ?,
                      validado_por = ?, validado_en = datetime('now'), motivo_rechazo = NULL,
                      actualizado_en = datetime('now')
               WHERE id = ?""",
            (cupo, max(0, cupo - ocupados), horas, plan,
             str(d.get("area_responsable", "")).strip() or p["area_responsable"],
             str(d.get("objetivo", "")).strip() or p["objetivo"],
             session["usuario_id"], programa_id))

        if not servicios:
            # Caso excepcional: la propuesta es válida pero no tenía servicio.
            servicio_id = con.execute(
                "INSERT INTO servicios_sociales (alumno_id, programa_id, estatus, horas_requeridas) "
                "VALUES (?, ?, 'PENDIENTE', ?)", (alumno_id, programa_id, horas)).lastrowid
        else:
            servicio_id = servicios[0]["id"]

        notificar(con, alumno_id,
                  f"Su propuesta propia \"{p['nombre']}\" fue aprobada y publicada en el banco.")
        registrar_bitacora(con, session["usuario_id"], "APROBAR_PROPUESTA",
                           f"Programa ID {programa_id}, servicio {servicio_id}")
    return jsonify({"ok": True, "servicio_id": servicio_id,
                    "mensaje": "Propuesta aprobada y agregada al banco"})


# ================================================ Revisión de documentos (CU10)
@jefe_bp.get("/api/jefe/documentos")
@login_requerido(JEFE)
def jefe_listar_documentos():
    estatus = request.args.get("estatus", "PENDIENTE").strip().upper()
    where, params = "d.estatus <> 'REEMPLAZADO'", []
    if estatus in ("PENDIENTE", "VALIDADO", "OBSERVADO"):
        where += " AND d.estatus = ?"
        params.append(estatus)
    elif estatus not in ("", "TODOS", "TODAS"):
        return error("Estatus no válido", 400)

    with closing(conectar()) as con:
        filas = con.execute(
            f"""SELECT d.id, d.tipo, d.numero_reporte, d.version, d.estatus,
                       d.nombre_original, d.subido_en, d.revisado_en,
                       {NOMBRE_SQL} AS alumno_nombre, u.identificador AS alumno_control,
                       p.nombre AS programa_nombre, d.servicio_id,
                       (SELECT texto FROM observaciones o WHERE o.documento_id = d.id
                        ORDER BY o.id DESC LIMIT 1) AS observacion
                FROM documentos d
                JOIN servicios_sociales ss ON d.servicio_id = ss.id
                JOIN usuarios u ON ss.alumno_id = u.id
                JOIN programas p ON ss.programa_id = p.id
                WHERE {where} ORDER BY d.subido_en ASC, d.id ASC""", params).fetchall()
    return jsonify([dict(r) for r in filas])


@jefe_bp.get("/api/jefe/documentos/<int:documento_id>/archivo")
@login_requerido(JEFE)
def jefe_ver_documento(documento_id):
    with closing(conectar()) as con:
        fila = con.execute(
            "SELECT ruta_archivo, nombre_original, estatus FROM documentos WHERE id = ?",
            (documento_id,)).fetchone()
    ruta = archivos.ruta_segura(fila["ruta_archivo"]) if fila else None
    if not ruta or not ruta.is_file():
        return error("Documento no encontrado", 404)
    return send_file(ruta, mimetype="application/pdf", as_attachment=False,
                     download_name=fila["nombre_original"])


@jefe_bp.post("/api/jefe/documentos/<int:documento_id>/revisar")
@login_requerido(JEFE)
def jefe_revisar_documento(documento_id):
    """VALIDAR el documento u OBSERVAR (con comentarios) para que el alumno lo corrija."""
    d = _datos()
    accion = str(d.get("accion", "")).strip().upper()
    texto = str(d.get("texto", "")).strip()
    if accion not in ("VALIDAR", "OBSERVAR"):
        return error("Acción no válida", 400)
    if accion == "OBSERVAR" and not texto:
        return error("Escriba las observaciones para que el alumno sepa qué corregir", 400)
    if len(texto) > 2000:
        return error("Las observaciones no pueden pasar de 2000 caracteres", 400)

    nuevo = "VALIDADO" if accion == "VALIDAR" else "OBSERVADO"
    with transaccion() as con:
        doc = con.execute(
            """SELECT d.tipo, d.numero_reporte, d.estatus, d.servicio_id, ss.alumno_id
               FROM documentos d JOIN servicios_sociales ss ON ss.id = d.servicio_id
               WHERE d.id = ?""", (documento_id,)).fetchone()
        if not doc:
            return error("Documento no encontrado", 404)
        cur = con.execute(
            "UPDATE documentos SET estatus = ?, revisado_por = ?, revisado_en = datetime('now') "
            "WHERE id = ? AND estatus = 'PENDIENTE'",
            (nuevo, session["usuario_id"], documento_id))
        if cur.rowcount == 0:
            return error("Este documento ya fue revisado o fue reemplazado por el alumno", 409)

        nombre = _nombre_documento(doc["tipo"], doc["numero_reporte"])
        if accion == "OBSERVAR":
            con.execute("INSERT INTO observaciones (documento_id, autor_id, texto) VALUES (?, ?, ?)",
                        (documento_id, session["usuario_id"], texto))
            notificar(con, doc["alumno_id"],
                      f"Su documento \"{nombre}\" tiene observaciones: {texto}")
        else:
            notificar(con, doc["alumno_id"], f"Su documento \"{nombre}\" fue validado")
            if doc["tipo"] in ("MEMORIA_FINAL", "CARTA_TERMINACION"):
                notificar_rol(con, "JEFE_VINCULACION",
                              f"El documento \"{nombre}\" del alumno (servicio "
                              f"{doc['servicio_id']}) fue validado.")
        concluido = quizas_concluir(con, doc["servicio_id"]) if accion == "VALIDAR" else False
        registrar_bitacora(con, session["usuario_id"], "REVISAR_DOCUMENTO",
                           f"Documento ID {documento_id}: {nuevo}")
    mensaje = "Documento validado" if accion == "VALIDAR" else "Observaciones enviadas al alumno"
    if concluido:
        mensaje += ". El servicio social quedó CONCLUIDO; Vinculación puede emitir la constancia."
    return jsonify({"ok": True, "mensaje": mensaje, "concluido": concluido})


# ================================================== Servicios y horas (RF-08/14/16)
@jefe_bp.get("/api/jefe/servicios")
@login_requerido(JEFE)
def jefe_listar_servicios():
    q = request.args.get("q", "").strip()
    estatus = request.args.get("estatus", "").strip().upper()
    condiciones, params = [], []
    if q:
        condiciones.append(f"({NOMBRE_SQL} LIKE ? OR u.identificador LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if estatus in ("PENDIENTE", "ACTIVO", "CONCLUIDO", "LIBERADO", "BAJA"):
        condiciones.append("s.estatus = ?")
        params.append(estatus)
    where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""

    with closing(conectar()) as con:
        filas = con.execute(
            f"""SELECT s.id, s.estatus, s.fecha_inicio, s.fecha_fin, s.horas_requeridas,
                       s.plan_id, u.identificador, {NOMBRE_SQL} AS alumno_nombre,
                       a.carrera, a.plan_estudios, p.id AS programa_id, p.nombre AS programa,
                       p.origen, e.nombre AS empresa,
                       COALESCE((SELECT SUM(h.horas) FROM registro_horas h
                                 WHERE h.servicio_id = s.id), 0) AS horas_acumuladas
                FROM servicios_sociales s
                JOIN usuarios u ON u.id = s.alumno_id
                JOIN alumnos a ON a.usuario_id = s.alumno_id
                JOIN programas p ON p.id = s.programa_id
                JOIN empresas_receptoras e ON e.id = p.empresa_id
                {where} ORDER BY s.id DESC""", params).fetchall()
        resultado = []
        for fila in filas:
            item = dict(fila)
            item.update(avance_horas(con, fila))
            item["documentos_faltantes"] = len(documentos_faltantes(con, fila["id"]))
            resultado.append(item)
    return jsonify(resultado)


@jefe_bp.patch("/api/jefe/servicios/<int:servicio_id>")
@login_requerido(JEFE)
def jefe_editar_servicio(servicio_id):
    """RF-14: registrar fechas oficiales, activar o asignar un plan."""
    d = _datos()
    with transaccion() as con:
        s = _servicio(con, servicio_id)
        if not s:
            return error("Servicio social no encontrado", 404)
        if s["estatus"] == "BAJA":
            return error("No se puede modificar un servicio dado de baja", 409)
        if s["estatus"] == "LIBERADO":
            return error("El servicio ya fue liberado y no se puede modificar", 409)

        fecha_inicio = str(d.get("fecha_inicio", s["fecha_inicio"] or "")).strip() or None
        fecha_fin = str(d.get("fecha_fin", s["fecha_fin"] or "")).strip() or None
        estatus = str(d.get("estatus", s["estatus"])).strip().upper()
        plan_id = d.get("plan_id", s["plan_id"])

        for fecha, nombre in ((fecha_inicio, "fecha de inicio"), (fecha_fin, "fecha de fin")):
            if fecha and (err := validar_fecha(fecha, nombre)):
                return error(err, 400)
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            return error("La fecha de inicio no puede ser posterior a la fecha de fin", 400)
        if estatus not in ("PENDIENTE", "ACTIVO", "CONCLUIDO"):
            return error("Estatus no válido para esta operación", 400)
        if fecha_inicio and fecha_fin:
            traslape = con.execute(
                """SELECT id FROM servicios_sociales
                   WHERE alumno_id = ? AND id <> ? AND estatus <> 'BAJA'
                     AND fecha_inicio IS NOT NULL AND fecha_fin IS NOT NULL
                     AND fecha_inicio <= ? AND fecha_fin >= ?
                   ORDER BY id LIMIT 1""",
                (s["alumno_id"], servicio_id, fecha_fin, fecha_inicio)).fetchone()
            if traslape:
                return error("El periodo se traslapa con otro servicio social del mismo "
                             f"alumno (servicio {traslape['id']})", 409)
        if estatus == "ACTIVO" and not fecha_inicio:
            fecha_inicio = date.today().isoformat()
        if plan_id in ("", None):
            plan_id = None
        elif not con.execute("SELECT 1 FROM planes_servicio WHERE id = ? AND activo = 1",
                             (plan_id,)).fetchone():
            return error("El plan de servicio social no existe o está inactivo", 400)

        if estatus == "CONCLUIDO":
            if horas_acumuladas(con, servicio_id) < s["horas_requeridas"]:
                return error("No se puede concluir: faltan horas por registrar", 409)
            faltantes = documentos_faltantes(con, servicio_id)
            if faltantes:
                return error("No se puede concluir: hay documentos faltantes o sin validar", 409)

        con.execute(
            """UPDATE servicios_sociales SET estatus = ?, fecha_inicio = ?, fecha_fin = ?,
                      plan_id = ?, actualizado_en = datetime('now') WHERE id = ?""",
            (estatus, fecha_inicio, fecha_fin, plan_id, servicio_id))
        notificar(con, s["alumno_id"],
                  f"Su servicio social fue actualizado a estatus {estatus}.")
        registrar_bitacora(con, session["usuario_id"], "EDITAR_SERVICIO",
                           f"Servicio {servicio_id}: {estatus}")
    return jsonify({"ok": True, "mensaje": "Servicio social actualizado correctamente"})


@jefe_bp.post("/api/jefe/servicios/<int:servicio_id>/baja")
@login_requerido(JEFE)
def jefe_baja_servicio(servicio_id):
    motivo = str(_datos().get("motivo", "")).strip()
    if not motivo:
        return error("Indique el motivo de la baja", 400)
    with transaccion() as con:
        s = _servicio(con, servicio_id)
        if not s:
            return error("Servicio social no encontrado", 404)
        if s["estatus"] not in ("PENDIENTE", "ACTIVO"):
            return error("Solo se puede dar de baja un servicio pendiente o activo", 409)
        if not con.execute("SELECT 1 FROM bajas WHERE servicio_id = ?",
                           (servicio_id,)).fetchone():
            con.execute("INSERT INTO bajas (servicio_id, motivo, registrada_por) VALUES (?, ?, ?)",
                        (servicio_id, motivo, session["usuario_id"]))
        con.execute("UPDATE servicios_sociales SET estatus = 'BAJA', "
                    "actualizado_en = datetime('now') WHERE id = ?", (servicio_id,))
        liberar_cupo(con, s["programa_id"])
        notificar(con, s["alumno_id"],
                  f"Su servicio social fue dado de baja por la Oficina de SS. Motivo: {motivo}")
        registrar_bitacora(con, session["usuario_id"], "BAJA_SERVICIO",
                           f"Servicio {servicio_id}: {motivo}")
    return jsonify({"ok": True, "mensaje": "Servicio social dado de baja"})


@jefe_bp.get("/api/jefe/servicios/<int:servicio_id>/horas")
@login_requerido(JEFE)
def jefe_listar_horas(servicio_id):
    with closing(conectar()) as con:
        s = _servicio(con, servicio_id)
        if not s:
            return error("Servicio social no encontrado", 404)
        filas = con.execute(
            f"""SELECT h.id, h.fecha, h.horas, {NOMBRE_SQL} AS registrada_por,
                       h.creado_en
                FROM registro_horas h JOIN usuarios u ON u.id = h.registrada_por
                WHERE h.servicio_id = ? ORDER BY h.fecha DESC, h.id DESC""",
            (servicio_id,)).fetchall()
        resumen = avance_horas(con, s)
    return jsonify({"horas": [dict(f) for f in filas], **resumen})


@jefe_bp.post("/api/jefe/servicios/<int:servicio_id>/horas")
@login_requerido(JEFE)
def jefe_registrar_horas(servicio_id):
    d = _datos()
    fecha = str(d.get("fecha", date.today().isoformat())).strip()
    horas = _entero(d.get("horas"), minimo=1, maximo=24)
    if err := validar_fecha(fecha, "fecha"):
        return error(err, 400)
    if horas is None:
        return error("Las horas deben ser un número entero entre 1 y 24", 400)

    with transaccion() as con:
        s = _servicio(con, servicio_id)
        if not s:
            return error("Servicio social no encontrado", 404)
        if s["estatus"] != "ACTIVO":
            return error("Solo se registran horas de un servicio activo", 409)
        con.execute(
            "INSERT INTO registro_horas (servicio_id, fecha, horas, registrada_por) "
            "VALUES (?, ?, ?, ?)", (servicio_id, fecha, horas, session["usuario_id"]))
        total = horas_acumuladas(con, servicio_id)
        notificar(con, s["alumno_id"],
                  f"Se registraron {horas} hora(s) de servicio social. "
                  f"Acumulado: {total} de {s['horas_requeridas']}.")
        concluido = quizas_concluir(con, servicio_id)
        registrar_bitacora(con, session["usuario_id"], "REGISTRAR_HORAS",
                           f"Servicio {servicio_id}: +{horas} horas")
    return jsonify({"ok": True, "mensaje": "Horas registradas correctamente",
                    "horas_acumuladas": total, "concluido": concluido})


# ==================================== Periodos de entrega (RF-09, globales)
# La misma fecha aplica a TODOS los alumnos. Los 3 reportes van por separado.
DOCUMENTOS_PERIODO = (("CARTA_PRESENTACION", 0), ("SOLICITUD", 0),
                      ("CARTA_ACEPTACION", 0), ("REPORTE_BIMESTRAL", 1),
                      ("REPORTE_BIMESTRAL", 2), ("REPORTE_BIMESTRAL", 3),
                      ("MEMORIA_FINAL", 0), ("CARTA_TERMINACION", 0))


def _estado_periodo(fila, hoy):
    if fila is None:
        return "SIN_PERIODO"
    if hoy < fila["fecha_inicio"]:
        return "PROGRAMADO"
    if hoy > fila["fecha_fin"]:
        return "VENCIDO"
    return "ABIERTO"


def _notificar_alumnos_vigentes(con, mensaje):
    """Avisa a los alumnos con servicio vigente (la fecha es para todos)."""
    for fila in con.execute(
            "SELECT DISTINCT alumno_id FROM servicios_sociales "
            "WHERE estatus IN ('PENDIENTE','ACTIVO')"):
        notificar(con, fila["alumno_id"], mensaje)


@jefe_bp.get("/api/jefe/periodos")
@login_requerido(JEFE)
def jefe_listar_periodos():
    """Fechas de entrega de cada documento (iguales para todos los alumnos)."""
    with closing(conectar()) as con:
        guardados = {(f["tipo"], f["numero_reporte"]): f for f in con.execute(
            "SELECT tipo, numero_reporte, fecha_inicio, fecha_fin FROM periodos_entrega")}
        hoy = date.today().isoformat()
        resultado = []
        for tipo, numero in DOCUMENTOS_PERIODO:
            f = guardados.get((tipo, numero))
            resultado.append({
                "tipo": tipo, "numero_reporte": numero,
                "titulo": _nombre_documento(tipo, numero),
                "fecha_inicio": f["fecha_inicio"] if f else None,
                "fecha_fin": f["fecha_fin"] if f else None,
                "estado": _estado_periodo(f, hoy),
            })
    return jsonify(resultado)


@jefe_bp.post("/api/jefe/periodos")
@login_requerido(JEFE)
def jefe_definir_periodo():
    """RF-09: fecha única (para todos los alumnos) para subir un documento.

    Si no se envía ``fecha_fin`` se programa una semana (7 días con el de inicio).
    """
    d = _datos()
    tipo = str(d.get("tipo", "REPORTE_BIMESTRAL")).strip().upper()
    if tipo not in TIPOS_PLANTILLA:
        return error("Tipo de documento no válido", 400)
    if tipo == "REPORTE_BIMESTRAL":
        numero = _entero(d.get("numero_reporte"), minimo=1, maximo=3)
        if numero is None:
            return error("El número de reporte debe estar entre 1 y 3", 400)
    else:
        numero = 0

    inicio = str(d.get("fecha_inicio", "")).strip()
    fin = str(d.get("fecha_fin", "")).strip()
    if err := validar_fecha(inicio, "fecha de inicio"):
        return error(err, 400)
    if not fin:
        fin = (date.fromisoformat(inicio) + timedelta(days=6)).isoformat()
    if err := validar_fecha(fin, "fecha de fin"):
        return error(err, 400)
    if inicio > fin:
        return error("La fecha de inicio no puede ser posterior a la fecha de fin", 400)

    nombre_doc = _nombre_documento(tipo, numero)
    with transaccion() as con:
        con.execute(
            """INSERT INTO periodos_entrega
                   (tipo, numero_reporte, fecha_inicio, fecha_fin, definido_por)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tipo, numero_reporte) DO UPDATE SET
                   fecha_inicio = excluded.fecha_inicio,
                   fecha_fin = excluded.fecha_fin,
                   definido_por = excluded.definido_por,
                   actualizado_en = datetime('now')""",
            (tipo, numero, inicio, fin, session["usuario_id"]))
        _notificar_alumnos_vigentes(
            con, f"Se definió el periodo para subir {nombre_doc}: {inicio} a {fin}.")
        registrar_bitacora(con, session["usuario_id"], "DEFINIR_PERIODO",
                           f"{tipo} #{numero}: {inicio} a {fin} (todos los alumnos)")
    return jsonify({"ok": True, "mensaje": "Periodo de entrega guardado correctamente",
                    "fecha_inicio": inicio, "fecha_fin": fin})


@jefe_bp.post("/api/jefe/periodos/semana")
@login_requerido(JEFE)
def jefe_definir_semana():
    """Programa una semana (para todos los alumnos) a los documentos sin fecha."""
    d = _datos()
    inicio = str(d.get("fecha_inicio", "")).strip()
    if err := validar_fecha(inicio, "fecha de inicio"):
        return error(err, 400)
    fin = (date.fromisoformat(inicio) + timedelta(days=6)).isoformat()

    with transaccion() as con:
        ya = {(f["tipo"], f["numero_reporte"]) for f in con.execute(
            "SELECT tipo, numero_reporte FROM periodos_entrega")}
        creados = 0
        for tipo, numero in DOCUMENTOS_PERIODO:
            if (tipo, numero) in ya:
                continue
            con.execute(
                """INSERT INTO periodos_entrega
                       (tipo, numero_reporte, fecha_inicio, fecha_fin, definido_por)
                   VALUES (?, ?, ?, ?, ?)""",
                (tipo, numero, inicio, fin, session["usuario_id"]))
            creados += 1
        if not creados:
            return error("Todos los documentos ya tienen un periodo definido", 409)
        _notificar_alumnos_vigentes(
            con, f"Se programó una semana ({inicio} a {fin}) para subir sus documentos.")
        registrar_bitacora(con, session["usuario_id"], "DEFINIR_SEMANA",
                           f"{inicio} a {fin} ({creados} documentos, todos los alumnos)")
    return jsonify({"ok": True, "creados": creados,
                    "mensaje": f"Se programó una semana ({inicio} a {fin}) para "
                               f"{creados} documento(s)"})


# ==================================== Reportes bimestrales faltantes (CU11)
@jefe_bp.get("/api/jefe/reportes-faltantes")
@login_requerido(JEFE)
def jefe_reportes_faltantes():
    periodo = request.args.get("periodo", "").strip()
    carrera = request.args.get("carrera", "").strip()
    bimestre_arg = request.args.get("bimestre", "").strip()
    bimestres = [1, 2, 3]
    if bimestre_arg:
        numero = _entero(bimestre_arg, minimo=1, maximo=3)
        if numero is None:
            return error("El bimestre debe estar entre 1 y 3", 400)
        bimestres = [numero]

    condiciones = ["s.estatus = 'ACTIVO'"]
    params = []
    if periodo:
        condiciones.append("p.periodo = ?")
        params.append(periodo)
    if carrera:
        condiciones.append("a.carrera LIKE ?")
        params.append(f"%{carrera}%")
    hoy = date.today().isoformat()

    with closing(conectar()) as con:
        filas = con.execute(
            f"""SELECT s.id AS servicio_id, u.identificador, {NOMBRE_SQL} AS alumno_nombre,
                       a.carrera, p.nombre AS programa, p.periodo, s.horas_requeridas
                FROM servicios_sociales s
                JOIN usuarios u ON u.id = s.alumno_id
                JOIN alumnos a ON a.usuario_id = s.alumno_id
                JOIN programas p ON p.id = s.programa_id
                WHERE {' AND '.join(condiciones)}
                ORDER BY a.carrera, u.apellido_paterno, u.apellido_materno, u.nombre""",
            params).fetchall()

        faltantes = []
        for servicio in filas:
            for numero in bimestres:
                entrega = con.execute(
                    "SELECT fecha_fin FROM periodos_entrega "
                    "WHERE tipo = 'REPORTE_BIMESTRAL' AND numero_reporte = ?",
                    (numero,)).fetchone()
                if not entrega or entrega["fecha_fin"] >= hoy:
                    continue   # todavía no vence (o no se ha definido el periodo)
                doc = con.execute(
                    "SELECT estatus FROM documentos WHERE servicio_id = ? "
                    "AND tipo = 'REPORTE_BIMESTRAL' AND numero_reporte = ? "
                    "AND estatus <> 'REEMPLAZADO' ORDER BY version DESC, id DESC LIMIT 1",
                    (servicio["servicio_id"], numero)).fetchone()
                if doc and doc["estatus"] == "VALIDADO":
                    continue
                faltantes.append({
                    "servicio_id": servicio["servicio_id"],
                    "identificador": servicio["identificador"],
                    "alumno_nombre": servicio["alumno_nombre"],
                    "carrera": servicio["carrera"],
                    "programa": servicio["programa"],
                    "periodo": servicio["periodo"],
                    "bimestre": numero,
                    "fecha_fin": entrega["fecha_fin"],
                    "estatus_documento": doc["estatus"] if doc else "SIN_SUBIR",
                })

    if not faltantes:
        return jsonify({"faltantes": [], "total": 0,
                        "mensaje": "Todos los alumnos subieron su reporte bimestral"})
    return jsonify({"faltantes": faltantes, "total": len(faltantes),
                    "mensaje": "Reporte generado correctamente"})


# ================================================== Planes de servicio (RF-13)
@jefe_bp.get("/api/jefe/planes")
@login_requerido(JEFE)
def jefe_listar_planes():
    with closing(conectar()) as con:
        filas = con.execute(
            """SELECT p.*, (SELECT COUNT(*) FROM servicios_sociales s
                              WHERE s.plan_id = p.id) AS servicios
               FROM planes_servicio p ORDER BY p.nombre""").fetchall()
    return jsonify([dict(f) for f in filas])


def _validar_plan_servicio(d):
    nombre = str(d.get("nombre", "")).strip()
    actividades = str(d.get("actividades", "")).strip()
    cronograma = str(d.get("cronograma", "")).strip()
    horas = _entero(d.get("horas_por_periodo"), minimo=1, maximo=1000)
    if not nombre or not actividades or not cronograma:
        return None, "Nombre, actividades y cronograma son obligatorios"
    if len(nombre) > 150:
        return None, "El nombre del plan no puede pasar de 150 caracteres"
    if horas is None:
        return None, "Las horas por periodo deben ser un número entero mayor que 0"
    return (nombre, actividades, cronograma, horas), None


@jefe_bp.post("/api/jefe/planes")
@login_requerido(JEFE)
def jefe_crear_plan():
    valores, err = _validar_plan_servicio(_datos())
    if err:
        return error(err, 400)
    with transaccion() as con:
        if con.execute("SELECT 1 FROM planes_servicio WHERE nombre = ?",
                       (valores[0],)).fetchone():
            return error("Ya existe un plan con ese nombre", 409)
        plan_id = con.execute(
            """INSERT INTO planes_servicio (nombre, actividades, cronograma,
                   horas_por_periodo, creado_por) VALUES (?, ?, ?, ?, ?)""",
            (*valores, session["usuario_id"])).lastrowid
        registrar_bitacora(con, session["usuario_id"], "ALTA_PLAN",
                           f"Plan ID {plan_id}: {valores[0]}")
    return jsonify({"ok": True, "id": plan_id, "mensaje": "Plan creado correctamente"})


@jefe_bp.patch("/api/jefe/planes/<int:plan_id>")
@login_requerido(JEFE)
def jefe_editar_plan(plan_id):
    with transaccion() as con:
        plan = con.execute("SELECT * FROM planes_servicio WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            return error("Plan no encontrado", 404)
        datos = dict(plan)
        datos.update(_datos())
        valores, err = _validar_plan_servicio(datos)
        if err:
            return error(err, 400)
        activo = 1 if _datos().get("activo", plan["activo"]) else 0
        if con.execute("SELECT 1 FROM planes_servicio WHERE nombre = ? AND id <> ?",
                       (valores[0], plan_id)).fetchone():
            return error("Ya existe otro plan con ese nombre", 409)
        con.execute(
            """UPDATE planes_servicio SET nombre = ?, actividades = ?, cronograma = ?,
                      horas_por_periodo = ?, activo = ? WHERE id = ?""",
            (*valores, activo, plan_id))
        registrar_bitacora(con, session["usuario_id"], "EDITAR_PLAN",
                           f"Plan ID {plan_id}: {valores[0]}")
    return jsonify({"ok": True, "mensaje": "Plan actualizado correctamente"})


@jefe_bp.delete("/api/jefe/planes/<int:plan_id>")
@login_requerido(JEFE)
def jefe_eliminar_plan(plan_id):
    with transaccion() as con:
        plan = con.execute("SELECT nombre FROM planes_servicio WHERE id = ?",
                           (plan_id,)).fetchone()
        if not plan:
            return error("Plan no encontrado", 404)
        en_uso = con.execute("SELECT COUNT(*) FROM servicios_sociales WHERE plan_id = ?",
                             (plan_id,)).fetchone()[0]
        if en_uso:
            return error("No se puede eliminar un plan que está en uso", 409)
        con.execute("DELETE FROM planes_servicio WHERE id = ?", (plan_id,))
        registrar_bitacora(con, session["usuario_id"], "ELIMINAR_PLAN",
                           f"Plan ID {plan_id}: {plan['nombre']}")
    return jsonify({"ok": True, "mensaje": "Plan eliminado correctamente"})


# ================================================= Curso de inducción (CU03)
@jefe_bp.get("/api/jefe/induccion")
@login_requerido(JEFE)
def jefe_listar_induccion():
    with closing(conectar()) as con:
        filas = con.execute(
            """SELECT c.*,
                      (SELECT COUNT(*) FROM asistencias_induccion a WHERE a.curso_id = c.id)
                          AS asistentes,
                      (SELECT COUNT(*) FROM asistencias_induccion a
                        WHERE a.curso_id = c.id AND a.forms_completos = 1) AS forms
               FROM cursos_induccion c ORDER BY c.fecha DESC, c.id DESC""").fetchall()
    return jsonify([dict(f) for f in filas])


@jefe_bp.post("/api/jefe/induccion")
@login_requerido(JEFE)
def jefe_crear_induccion():
    d = _datos()
    fecha = str(d.get("fecha", "")).strip()
    periodo = str(d.get("periodo", "")).strip()
    lugar = str(d.get("lugar", "")).strip() or None
    if err := (validar_fecha(fecha, "fecha") or validar_periodo(periodo)):
        return error(err, 400)
    with transaccion() as con:
        if con.execute("SELECT 1 FROM cursos_induccion WHERE periodo = ?",
                       (periodo,)).fetchone():
            return error("Ya existe un curso de inducción para ese periodo", 409)
        curso_id = con.execute(
            "INSERT INTO cursos_induccion (fecha, lugar, periodo) VALUES (?, ?, ?)",
            (fecha, lugar, periodo)).lastrowid
        registrar_bitacora(con, session["usuario_id"], "ALTA_INDUCCION",
                           f"Curso ID {curso_id}, periodo {periodo}")
    return jsonify({"ok": True, "id": curso_id, "mensaje": "Curso de inducción creado"})


@jefe_bp.post("/api/jefe/induccion/<int:curso_id>/qr")
@login_requerido(JEFE)
def jefe_generar_qr(curso_id):
    """Genera un token de asistencia vigente 10 segundos (CU03)."""
    ahora = datetime.now(timezone.utc)
    expira = ahora + timedelta(seconds=10)
    token = uuid.uuid4().hex
    with transaccion() as con:
        curso = con.execute("SELECT * FROM cursos_induccion WHERE id = ?",
                            (curso_id,)).fetchone()
        if not curso:
            return error("Curso de inducción no encontrado", 404)
        if not curso["activo"]:
            return error("El curso de inducción está inactivo", 409)
        con.execute(
            "UPDATE cursos_induccion SET qr_token = ?, qr_generado_en = ?, qr_expira_en = ? "
            "WHERE id = ?",
            (token, ahora.strftime("%Y-%m-%d %H:%M:%S"),
             expira.strftime("%Y-%m-%d %H:%M:%S"), curso_id))
        registrar_bitacora(con, session["usuario_id"], "QR_INDUCCION",
                           f"Curso {curso_id}, expira {expira:%Y-%m-%d %H:%M:%S}")
    return jsonify({"ok": True, "token": token,
                    "contenido": f"SISTEMASS-INDUCCION:{token}",
                    "generado_en": ahora.strftime("%Y-%m-%d %H:%M:%S"),
                    "expira_en": expira.strftime("%Y-%m-%d %H:%M:%S"),
                    "segundos_vigencia": 10})


@jefe_bp.get("/api/jefe/induccion/<int:curso_id>/asistencias")
@login_requerido(JEFE)
def jefe_asistencias_induccion(curso_id):
    with closing(conectar()) as con:
        if not con.execute("SELECT 1 FROM cursos_induccion WHERE id = ?",
                           (curso_id,)).fetchone():
            return error("Curso de inducción no encontrado", 404)
        filas = con.execute(
            f"""SELECT a.alumno_id, u.identificador, {NOMBRE_SQL} AS alumno_nombre,
                       al.carrera, a.forms_completos, a.registrada_en,
                       (SELECT f.enviado_en FROM forms_induccion f
                         WHERE f.curso_id = a.curso_id AND f.alumno_id = a.alumno_id)
                           AS forms_enviado_en
                FROM asistencias_induccion a
                JOIN usuarios u ON u.id = a.alumno_id
                JOIN alumnos al ON al.usuario_id = a.alumno_id
                WHERE a.curso_id = ? ORDER BY u.apellido_paterno, u.apellido_materno, u.nombre""",
            (curso_id,)).fetchall()
    return jsonify([dict(f) for f in filas])


# ==================================================================== Resumen
@jefe_bp.get("/api/jefe/resumen")
@login_requerido(JEFE)
def jefe_resumen():
    with closing(conectar()) as con:
        contar = lambda sql, *params: con.execute(sql, params).fetchone()[0]
        datos = {
            "propuestas_pendientes": contar(
                "SELECT COUNT(*) FROM programas WHERE tipo = 'PROPIA' AND estatus = 'PENDIENTE'"),
            "documentos_pendientes": contar(
                "SELECT COUNT(*) FROM documentos WHERE estatus = 'PENDIENTE'"),
            "programas_banco": contar(
                "SELECT COUNT(*) FROM programas WHERE tipo = 'BANCO' AND estatus = 'DISPONIBLE'"),
            "servicios_activos": contar(
                "SELECT COUNT(*) FROM servicios_sociales WHERE estatus = 'ACTIVO'"),
            "servicios_pendientes": contar(
                "SELECT COUNT(*) FROM servicios_sociales WHERE estatus = 'PENDIENTE'"),
            "alumnos": contar("SELECT COUNT(*) FROM usuarios WHERE rol = 'ALUMNO' AND activo = 1"),
        }
        recientes = con.execute(
            f"""SELECT b.fecha, {NOMBRE_SQL} AS usuario, b.accion, b.detalle
                FROM bitacora b LEFT JOIN usuarios u ON u.id = b.usuario_id
                ORDER BY b.id DESC LIMIT 8""").fetchall()
        datos["actividad_reciente"] = [dict(r) for r in recientes]
    return jsonify(datos)
