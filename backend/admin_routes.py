import io
import math
import re
import unicodedata
from datetime import date
from pathlib import Path

from flask import Blueprint, jsonify, request, session
from openpyxl import load_workbook
from werkzeug.security import generate_password_hash

from backend.db import registrar_bitacora, transaccion
from backend.rutas import archivos
from backend.seguridad import ROLES, error, login_requerido
from backend.validaciones import (
    calcular_porcentaje_creditos, correo_de_alumno, generar_password, unir_nombre,
    validar_correo_institucional, validar_creditos, validar_curp, validar_nombres,
    validar_numero_control, validar_password, validar_semestre, validar_telefono,
)

admin_bp = Blueprint("admin_bp", __name__)
# Límite de 5 MB para no saturar el servidor si suben un archivo muy pesado
MAX_BYTES_ARCHIVO = 5 * 1024 * 1024
# Atajo de SQL para juntar nombre y apellidos limpios sin espacios extras
NOMBRE_SQL = "trim(u.nombre || ' ' || u.apellido_paterno || ' ' || u.apellido_materno)"


# Resumen de métricas para la pantalla de inicio del admin
@admin_bp.get("/api/admin/resumen")
@login_requerido("ADMINISTRADOR")
def admin_resumen():
    with transaccion() as con:
        total_usuarios = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        prog_banco = con.execute("SELECT COUNT(*) FROM programas WHERE tipo = 'BANCO'").fetchone()[0]
        exp_activos = con.execute(
            "SELECT COUNT(*) FROM servicios_sociales WHERE estatus = 'ACTIVO'").fetchone()[0]
        por_rol = {r["rol"]: r["cantidad"] for r in con.execute(
            "SELECT rol, COUNT(*) AS cantidad FROM usuarios GROUP BY rol")}
        actividad = con.execute(
            f"""SELECT b.fecha, {NOMBRE_SQL} AS usuario, b.accion, b.detalle
                FROM bitacora b LEFT JOIN usuarios u ON b.usuario_id = u.id
                ORDER BY b.id DESC LIMIT 10""").fetchall()

    return jsonify({
        "usuarios": total_usuarios,
        "programas_banco": prog_banco,
        "expedientes_activos": exp_activos,
        "por_rol": por_rol,
        "actividad_reciente": [
            {"fecha": r["fecha"], "usuario": r["usuario"] or "Sistema",
             "accion": r["accion"], "detalle": r["detalle"]} for r in actividad],
    })


# Lista de usuarios con paginador y filtros de búsqueda
@admin_bp.get("/api/admin/usuarios")
@login_requerido("ADMINISTRADOR")
def admin_listar_usuarios():
    q = request.args.get("q", "").strip()
    rol = request.args.get("rol", "").strip()
    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        pagina = 1
    por_pagina = 10

    condiciones, params = [], []
    if q:
        condiciones.append(f"({NOMBRE_SQL} LIKE ? OR u.identificador LIKE ? OR u.correo LIKE ?)")
        params += [f"%{q}%"] * 3
    if rol in ROLES:
        condiciones.append("u.rol = ?")
        params.append(rol)
    where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""

    with transaccion() as con:
        total = con.execute(f"SELECT COUNT(*) FROM usuarios u {where}", params).fetchone()[0]
        paginas = max(1, math.ceil(total / por_pagina))
        pagina = min(pagina, paginas)
        filas = con.execute(
            f"""SELECT u.id, u.identificador, u.nombre, u.apellido_paterno, u.apellido_materno,
                       u.correo, u.rol, u.activo, u.debe_cambiar_password,
                       a.plan_estudios, a.creditos, a.carrera, a.semestre
                FROM usuarios u LEFT JOIN alumnos a ON a.usuario_id = u.id
                {where} ORDER BY u.id DESC LIMIT ? OFFSET ?""",
            params + [por_pagina, (pagina - 1) * por_pagina]).fetchall()

    usuarios = [{
        "id": r["id"],
        "identificador": r["identificador"],
        "nombre": r["nombre"],
        "apellido_paterno": r["apellido_paterno"],
        "apellido_materno": r["apellido_materno"],
        "nombre_completo": unir_nombre(r["nombre"], r["apellido_paterno"], r["apellido_materno"]),
        "correo": r["correo"],
        "rol": r["rol"],
        "activo": bool(r["activo"]),
        "debe_cambiar_password": bool(r["debe_cambiar_password"]),
        "carrera": r["carrera"],
        "semestre": r["semestre"],
        "plan_estudios": r["plan_estudios"],
        "creditos": r["creditos"],
        # alumno al que aún le falta que el admin capture plan y créditos
        "academicos_pendientes": r["rol"] == "ALUMNO" and
                                 (r["plan_estudios"] is None or r["creditos"] is None),
    } for r in filas]

    return jsonify({"usuarios": usuarios, "pagina": pagina, "paginas": paginas, "total": total})


# Registro manual de usuarios (personal o alumnos)
def _crear_alumno(d, nombre, ap_pat, ap_mat, control):

    curp = str(d.get("curp", "")).strip().upper()
    carrera = str(d.get("carrera", "")).strip()
    telefono = re.sub(r"\D", "", str(d.get("telefono", "")))
    domicilio = str(d.get("domicilio", "")).strip()
    try:
        semestre = int(d.get("semestre"))
    except (TypeError, ValueError):
        semestre = 0

    err = (validar_nombres(nombre, ap_pat, ap_mat) or validar_numero_control(control)
           or validar_curp(curp) or validar_semestre(semestre)
           or (None if carrera else "La carrera es obligatoria"))
    if not err and telefono:
        err = validar_telefono(telefono)
    if err:
        return error(err, 400)

    correo = correo_de_alumno(control)
    with transaccion() as con:
        if con.execute("SELECT 1 FROM usuarios WHERE identificador = ? OR correo = ?",
                       (control, correo)).fetchone():
            return error("El número de control ya se encuentra registrado", 400)
        if con.execute("SELECT 1 FROM alumnos WHERE curp = ?", (curp,)).fetchone():
            return error("La CURP ya está registrada con otro número de control", 400)
        usuario_id = con.execute(

            (control, nombre, ap_pat, ap_mat, correo,
             generate_password_hash(curp))).lastrowid
        con.execute(
           
            (usuario_id, curp, carrera, semestre, telefono or None, domicilio or None))
        registrar_bitacora(con, session["usuario_id"], "ALTA_USUARIO",
                           f"Alumno registrado manualmente: {control}")
    return jsonify({
        "ok": True,
        "mensaje": "Alumno registrado correctamente. Entra con su número de control y "
                   "su CURP como contraseña. Capture sus datos académicos "
                   "(plan y créditos) para que pueda elegir programa",
        "correo": correo,
        "curp": curp})


@admin_bp.post("/api/admin/usuarios")
@login_requerido("ADMINISTRADOR")
def admin_crear_usuario():
    d = request.get_json(silent=True) or {}
    nombre = str(d.get("nombre", "")).strip()
    ap_pat = str(d.get("apellido_paterno", "")).strip()
    ap_mat = str(d.get("apellido_materno", "")).strip()
    identificador = str(d.get("identificador", "")).strip()
    rol = str(d.get("rol", "")).strip()
    correo = str(d.get("correo", "")).strip().lower()
    password = str(d.get("password", ""))

    if not identificador or not rol:
        return error("Todos los campos son obligatorios", 400)
    if rol not in ROLES:
        return error("Rol no válido", 400)
    if rol == "ALUMNO":
        return _crear_alumno(d, nombre, ap_pat, ap_mat, identificador)
    if not correo or not password:
        return error("Todos los campos son obligatorios", 400)
    err = (validar_nombres(nombre, ap_pat, ap_mat) or validar_correo_institucional(correo)
           or validar_password(password))
    if err:
        return error(err, 400)

    with transaccion() as con:
        if con.execute("SELECT 1 FROM usuarios WHERE identificador = ? OR correo = ?",
                       (identificador, correo)).fetchone():
            return error("El usuario (número de empleado) o el correo ya se encuentra registrado", 400)
        con.execute(
           
            (identificador, nombre, ap_pat, ap_mat, correo, generate_password_hash(password), rol))
        registrar_bitacora(con, session["usuario_id"], "ALTA_USUARIO",
                           f"Usuario creado: {identificador} ({rol})")
    return jsonify({"ok": True, "mensaje": "Usuario registrado correctamente"})


# Carga de alumnos desde el archivo Excel del Forms
COLUMNAS_FORMS = [
    ("apellido_paterno", ("paterno",)),
    ("apellido_materno", ("materno",)),
    ("numero_control", ("control",)),
    ("carrera", ("carrera",)),
    ("semestre", ("semestre",)),
    ("curp", ("curp",)),
    ("telefono", ("telefono", "celular")),
    ("domicilio", ("domicilio", "direccion")),
    ("nombre", ("nombre",)),
]
OBLIGATORIAS = ["nombre", "apellido_paterno", "apellido_materno", "numero_control",
                "carrera", "semestre", "curp"]


def _normalizar(texto):
    sin_acentos = unicodedata.normalize("NFD", str(texto or ""))
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", sin_acentos.lower())


def _texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _mapear_columnas(encabezados):

    mapa, norm_elegida = {}, {}
    for i, enc in enumerate(encabezados):
        norm = _normalizar(enc)
        for campo, palabras in COLUMNAS_FORMS:
            if any(p in norm for p in palabras):
                if campo not in mapa or (campo == "nombre" and norm_elegida[campo] == "nombre"
                                         and norm != "nombre"):
                    mapa[campo] = i
                    norm_elegida[campo] = norm
                break
    return mapa


@admin_bp.post("/api/admin/alumnos/importar")
@login_requerido("ADMINISTRADOR")
def admin_importar_alumnos():
    archivo = request.files.get("archivo")
    periodo = request.form.get("periodo", "").strip()
    fecha_curso = request.form.get("fecha", "").strip()

    if not archivo or not archivo.filename.lower().endswith(".xlsx"):
        return error("Seleccione el archivo Excel (.xlsx) descargado de Forms", 400)
    if not re.fullmatch(r"\d{4}-[1-3]", periodo):
        return error("El periodo del curso debe tener el formato AAAA-N (ej. 2026-2)", 400)
    try:
        date.fromisoformat(fecha_curso)
    except ValueError:
        return error("Indique la fecha en que se impartió el curso de inducción", 400)

    contenido = archivo.read()
    if len(contenido) > MAX_BYTES_ARCHIVO:
        return error("El archivo excede el tamaño máximo de 5 MB", 400)
    try:
        hoja = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True).active
        filas = list(hoja.iter_rows(values_only=True))
    except Exception:
        return error("No se pudo leer el archivo. Verifique que sea un .xlsx válido", 400)
    if len(filas) < 2:
        return error("El archivo no contiene alumnos", 400)

    mapa = _mapear_columnas(filas[0])
    faltantes = [c for c in OBLIGATORIAS if c not in mapa]
    if faltantes:
        return error("Faltan columnas en el Excel: " + ", ".join(faltantes), 400)

    def dato(fila, campo):
        i = mapa.get(campo)
        return _texto(fila[i]) if i is not None and i < len(fila) else ""

    creados, omitidos, credenciales = 0, [], []
    vistos_control, vistos_curp = set(), set()

    with transaccion() as con:
        curso = con.execute("SELECT id FROM cursos_induccion WHERE periodo = ?", (periodo,)).fetchone()
        curso_id = curso["id"] if curso else con.execute(
            "INSERT INTO cursos_induccion (fecha, periodo) VALUES (?, ?)",
            (fecha_curso, periodo)).lastrowid

        for numero, fila in enumerate(filas[1:], start=2):      # número de fila como en Excel
            if not any(_texto(c) for c in fila):
                continue                                         # fila vacía
            nombre = dato(fila, "nombre")
            ap_pat = dato(fila, "apellido_paterno")
            ap_mat = dato(fila, "apellido_materno")
            control = re.sub(r"\D", "", dato(fila, "numero_control"))
            curp = dato(fila, "curp").upper()
            carrera = dato(fila, "carrera")
            telefono = re.sub(r"\D", "", dato(fila, "telefono"))
            domicilio = dato(fila, "domicilio")
            m = re.search(r"\d+", dato(fila, "semestre"))
            semestre = int(m.group()) if m else 0

            def omitir(motivo):
                omitidos.append({"fila": numero, "control": control or "—", "motivo": motivo})

            err = (validar_nombres(nombre, ap_pat, ap_mat) or validar_numero_control(control)
                   or validar_curp(curp) or validar_semestre(semestre)
                   or (None if carrera else "La carrera es obligatoria"))
            if not err and telefono:
                err = validar_telefono(telefono)
            if err:
                omitir(err)
                continue
            if control in vistos_control or curp in vistos_curp:
                omitir("Repetido dentro del mismo archivo")
                continue
            vistos_control.add(control)
            vistos_curp.add(curp)

            existente = con.execute("SELECT id, rol FROM usuarios WHERE identificador = ?",
                                    (control,)).fetchone()
            if existente:
                if existente["rol"] == "ALUMNO":
                    con.execute(
                        (curso_id, existente["id"]))
                    omitir("Ya estaba registrado (se registró su asistencia a este curso)")
                else:
                    omitir("El número ya pertenece a otro tipo de usuario")
                continue
            if con.execute("SELECT 1 FROM alumnos WHERE curp = ?", (curp,)).fetchone():
                omitir("La CURP ya está registrada con otro número de control")
                continue

            # El alumno entra con su CURP como contraseña (viene capturada en el Forms).
            password = curp
            usuario_id = con.execute(
                
                (control, nombre, ap_pat, ap_mat, correo_de_alumno(control),
                 generate_password_hash(password))).lastrowid
            con.execute(
                
                (usuario_id, curp, carrera, semestre, telefono or None, domicilio or None))
            con.execute(
                "INSERT INTO asistencias_induccion (curso_id, alumno_id, forms_completos) VALUES (?, ?, 1)",
                (curso_id, usuario_id))
            creados += 1
            credenciales.append({
                "identificador": control,
                "nombre": unir_nombre(nombre, ap_pat, ap_mat),
                "correo": correo_de_alumno(control),
                "password": password,
            })

        registrar_bitacora(con, session["usuario_id"], "IMPORTAR_ALUMNOS",
                           f"Periodo {periodo}: {creados} creados, {len(omitidos)} omitidos")

    return jsonify({"ok": True, "creados": creados, "omitidos": omitidos,
                    "credenciales": credenciales})


# Guarda el archivo subido en una carpeta protegida y regresa su ruta relativa
def _guardar_archivo(archivo, subcarpeta, prefijo, extensiones):

    nombre = archivo.filename or ""
    ext = Path(nombre).suffix.lower()
    if ext not in extensiones:
        return None, f"Formato no permitido (use {', '.join(extensiones)})"
    tamano = archivos.tamano(archivo)
    if tamano <= 0 or tamano > MAX_BYTES_ARCHIVO:
        return None, "El archivo está vacío o excede 5 MB"
    _, relativa = archivos.guardar(archivo, subcarpeta, ext)
    return relativa, None


@admin_bp.post("/api/admin/alumnos/<int:alumno_id>/academicos")
@login_requerido("ADMINISTRADOR")
def admin_datos_academicos(alumno_id):
    plan = request.form.get("plan_estudios", "").strip()
    try:
        creditos = int(request.form.get("creditos", ""))
    except ValueError:
        return error("Los créditos deben ser un número entero", 400)
    if plan not in ("NUEVO", "ANTIGUO"):
        return error("Seleccione el plan de servicio social", 400)
    err = validar_creditos(creditos)
    if err:
        return error(err, 400)

    with transaccion() as con:
        al = con.execute("SELECT * FROM alumnos WHERE usuario_id = ?", (alumno_id,)).fetchone()
        if not al:
            return error("Alumno no encontrado", 404)

        foto, boleta = al["foto_infantil"], al["boleta_extraescolares"]
        if plan == "ANTIGUO":
            f_foto, f_boleta = request.files.get("foto_infantil"), request.files.get("boleta_extraescolares")
            if f_foto and f_foto.filename:
                foto, err = _guardar_archivo(f_foto, f"alumnos/{alumno_id}", "foto", (".jpg", ".jpeg", ".png"))
                if err:
                    return error("Fotografía: " + err, 400)
            if f_boleta and f_boleta.filename:
                boleta, err = _guardar_archivo(f_boleta, f"alumnos/{alumno_id}", "boleta",
                                               (".pdf", ".jpg", ".jpeg", ".png"))
                if err:
                    return error("Boleta: " + err, 400)
            if not foto or not boleta:
                return error("Para plan antiguo la fotografía infantil y la boleta de extraescolares son obligatorias", 400)
        else:
            foto = boleta = None

        con.execute(
           
            (plan, creditos, calcular_porcentaje_creditos(creditos), foto, boleta, alumno_id))
        registrar_bitacora(con, session["usuario_id"], "DATOS_ACADEMICOS",
                           f"Alumno ID {alumno_id}: plan {plan}, {creditos} créditos")
    return jsonify({"ok": True, "mensaje": "Datos académicos guardados correctamente"})


# Modificar estado de la cuenta activo/inactivo
@admin_bp.patch("/api/admin/usuarios/<int:usuario_id>/estado")
@login_requerido("ADMINISTRADOR")
def admin_cambiar_estado_usuario(usuario_id):
    datos = request.get_json(silent=True) or {}
    activo = 1 if datos.get("activo") else 0
    if session["usuario_id"] == usuario_id:
        return error("No puede modificar el estatus de su propia cuenta", 400)

    with transaccion() as con:
        fila = con.execute("SELECT identificador FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        if not fila:
            return error("Usuario no encontrado", 404)
        con.execute("UPDATE usuarios SET activo = ? WHERE id = ?", (activo, usuario_id))
        registrar_bitacora(con, session["usuario_id"],
                           "ACTIVAR_USUARIO" if activo else "DESACTIVAR_USUARIO",
                           f"Usuario: {fila['identificador']}")
    return jsonify({"ok": True})

# En lugar de mandar correo de recuperación genera una clave temporal.
# Si es alumno, se la resetea directo a su CURP.
@admin_bp.post("/api/admin/usuarios/<int:usuario_id>/restablecer-password")
@login_requerido("ADMINISTRADOR")
def admin_restablecer_password(usuario_id):
   
    if session["usuario_id"] == usuario_id:
        return error("Use 'Cambiar contraseña' para su propia cuenta", 400)
    with transaccion() as con:
        fila = con.execute(
     
            (usuario_id,)).fetchone()
        if not fila:
            return error("Usuario no encontrado", 404)
        es_alumno = fila["rol"] == "ALUMNO" and fila["curp"]
        nueva = fila["curp"] if es_alumno else generar_password()
        con.execute(

            (generate_password_hash(nueva), 0 if es_alumno else 1, usuario_id))
        registrar_bitacora(con, session["usuario_id"], "RESTABLECER_PASSWORD",
                           f"Usuario: {fila['identificador']}"
                           + (" (contraseña = CURP)" if es_alumno else ""))
    return jsonify({
        "ok": True,
        "identificador": fila["identificador"],
        "password": nueva,
        "es_curp": bool(es_alumno)})
