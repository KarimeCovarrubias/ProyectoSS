"""Migra la base de datos existente al esquema corregido SIN perder informaciÃ³n.

Uso (desde la carpeta SistemaSS):
    .venv\\Scripts\\python.exe -m backend.migrar_bd

- Hace un respaldo de la base actual (servicio_social_backup_AAAAMMDD_HHMMSS.db).
- Crea una base nueva con backend/schema.sql.
- Copia usuarios, alumnos, cursos, empresas, programas, servicios, documentos,
  horas, constancias, notificaciones y bitÃ¡cora.
- Completa apellido materno / datos del titular que falten en registros viejos.
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUTA_BD = BASE / "servicio_social.db"
RUTA_SCHEMA = BASE / "schema.sql"
RUTA_NUEVA = BASE / "servicio_social_migrada.db"


def _columnas(con: sqlite3.Connection, tabla: str) -> set[str]:
    return {f[1] for f in con.execute(f"PRAGMA table_info({tabla})")}


def _tablas(con: sqlite3.Connection) -> set[str]:
    return {f[0] for f in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}


def _filas(con: sqlite3.Connection, tabla: str) -> list[sqlite3.Row]:
    return con.execute(f"SELECT * FROM {tabla}").fetchall()


def _partir_titular(texto: str) -> tuple[str, str, str]:
    """Divide un nombre completo viejo en nombre, apellido paterno y materno."""
    partes = [p for p in (texto or "").split() if p]
    if len(partes) >= 3:
        return " ".join(partes[:-2]), partes[-2], partes[-1]
    if len(partes) == 2:
        return partes[0], partes[1], "NO REGISTRADO"
    if len(partes) == 1:
        return partes[0], "NO REGISTRADO", "NO REGISTRADO"
    return "NO REGISTRADO", "NO REGISTRADO", "NO REGISTRADO"


def _texto_requerido(valor, respaldo="NO REGISTRADO") -> str:
    valor = (str(valor).strip() if valor is not None else "")
    return valor or respaldo


def _fecha(valor) -> str:
    return valor or datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def migrar() -> None:
    if not RUTA_BD.exists():
        raise SystemExit("No existe backend/servicio_social.db. Use crear_bd.py.")

    respaldo = BASE / f"servicio_social_backup_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(RUTA_BD, respaldo)
    print(f"Respaldo creado: {respaldo}")

    RUTA_NUEVA.unlink(missing_ok=True)
    nueva = sqlite3.connect(RUTA_NUEVA)
    nueva.row_factory = sqlite3.Row
    nueva.execute("PRAGMA foreign_keys = ON")
    nueva.executescript(RUTA_SCHEMA.read_text(encoding="utf-8"))

    vieja = sqlite3.connect(RUTA_BD)
    vieja.row_factory = sqlite3.Row
    tablas = _tablas(vieja)

    # ------------------------------------------------------------------ usuarios
    if "usuarios" in tablas:
        for u in _filas(vieja, "usuarios"):
            nueva.execute(
                """INSERT INTO usuarios (id, identificador, nombre, apellido_paterno,
                       apellido_materno, correo, password_hash, rol, activo,
                       debe_cambiar_password, intentos_fallidos, bloqueado_hasta, creado_en)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (u["id"], u["identificador"], _texto_requerido(u["nombre"]),
                 _texto_requerido(u["apellido_paterno"]),
                 _texto_requerido(u["apellido_materno"]), u["correo"], u["password_hash"],
                 u["rol"], u["activo"] if "activo" in u.keys() else 1,
                 u["debe_cambiar_password"] if "debe_cambiar_password" in u.keys() else 0,
                 u["intentos_fallidos"] if "intentos_fallidos" in u.keys() else 0,
                 u["bloqueado_hasta"] if "bloqueado_hasta" in u.keys() else None,
                 _fecha(u["creado_en"] if "creado_en" in u.keys() else None)))
        print(f"usuarios: {nueva.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]}")

    # ------------------------------------------------------------------- alumnos
    if "alumnos" in tablas:
        for a in _filas(vieja, "alumnos"):
            nueva.execute(
                """INSERT INTO alumnos (usuario_id, curp, carrera, semestre, telefono, domicilio,
                       plan_estudios, creditos, porcentaje_creditos, foto_infantil,
                       boleta_extraescolares)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (a["usuario_id"], a["curp"], a["carrera"], a["semestre"], a["telefono"],
                 a["domicilio"], a["plan_estudios"], a["creditos"], a["porcentaje_creditos"],
                 a["foto_infantil"], a["boleta_extraescolares"]))

    # --------------------------------------------------- cursos y asistencias
    if "cursos_induccion" in tablas:
        for c in _filas(vieja, "cursos_induccion"):
            cols = c.keys()
            nueva.execute(
                """INSERT INTO cursos_induccion (id, fecha, lugar, periodo, qr_token,
                       qr_generado_en, qr_expira_en, activo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (c["id"], c["fecha"], c["lugar"], c["periodo"],
                 c["qr_token"] if "qr_token" in cols else None,
                 c["qr_generado_en"] if "qr_generado_en" in cols else None,
                 c["qr_expira_en"] if "qr_expira_en" in cols else None,
                 c["activo"] if "activo" in cols else 1))
    if "asistencias_induccion" in tablas:
        for a in _filas(vieja, "asistencias_induccion"):
            nueva.execute(
                """INSERT INTO asistencias_induccion (id, curso_id, alumno_id, forms_completos,
                       registrada_en) VALUES (?, ?, ?, ?, ?)""",
                (a["id"], a["curso_id"], a["alumno_id"], a["forms_completos"],
                 a["registrada_en"]))
    if "forms_induccion" in tablas:
        for f in _filas(vieja, "forms_induccion"):
            nueva.execute(
                """INSERT INTO forms_induccion (id, curso_id, alumno_id, respuestas, enviado_en)
                   VALUES (?, ?, ?, ?, ?)""",
                (f["id"], f["curso_id"], f["alumno_id"], f["respuestas"], f["enviado_en"]))

    # ---------------------------------------------------------------- empresas
    if "empresas_receptoras" in tablas:
        for e in _filas(vieja, "empresas_receptoras"):
            cols = e.keys()
            if "titular_nombre" in cols:
                nombre, paterno, materno = (e["titular_nombre"], e["titular_apellido_paterno"],
                                            e["titular_apellido_materno"])
            else:
                nombre, paterno, materno = _partir_titular(e["titular"])
            completo = " ".join(x for x in (nombre, paterno, materno)
                                if x and x != "NO REGISTRADO") or "NO REGISTRADO"
            nueva.execute(
                """INSERT INTO empresas_receptoras (id, nombre, titular_nombre,
                       titular_apellido_paterno, titular_apellido_materno, titular, domicilio,
                       telefono) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (e["id"], _texto_requerido(e["nombre"]), nombre, paterno, materno, completo,
                 _texto_requerido(e["domicilio"], "Por definir"),
                 _texto_requerido(e["telefono"], "Por definir")))

    # ---------------------------------------------------------------- programas
    if "programas" in tablas:
        # Cada propuesta debe tener SU propia fila de empresa/responsable. Si la
        # base vieja comparte una empresa entre varias propuestas, se separa una
        # copia para cada una (así corregir un responsable no cambia los demás).
        empresas_usadas: set[int] = set()
        for p in _filas(vieja, "programas"):
            empresa_id = p["empresa_id"]
            if empresa_id is not None:
                if empresa_id in empresas_usadas:
                    emp = nueva.execute(
                        "SELECT * FROM empresas_receptoras WHERE id = ?",
                        (empresa_id,)).fetchone()
                    if emp:
                        empresa_id = nueva.execute(
                            """INSERT INTO empresas_receptoras
                                   (nombre, titular_nombre, titular_apellido_paterno,
                                    titular_apellido_materno, titular, domicilio, telefono)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (emp["nombre"], emp["titular_nombre"],
                             emp["titular_apellido_paterno"],
                             emp["titular_apellido_materno"], emp["titular"],
                             emp["domicilio"], emp["telefono"])).lastrowid
                else:
                    empresas_usadas.add(empresa_id)
            origen = p["origen"] if "origen" in p.keys() and p["origen"] else "INTERNA"
            nueva.execute(
                """INSERT INTO programas (id, tipo, origen, nombre, empresa_id,
                       area_responsable, objetivo, actividades, horas, cupo, cupo_disponible,
                       periodo, plan_estudios, estatus, creado_por, propuesto_por,
                       motivo_rechazo, validado_por, validado_en, creado_en)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (p["id"], p["tipo"], origen, p["nombre"], empresa_id,
                 p["area_responsable"], p["objetivo"], p["actividades"], p["horas"], p["cupo"],
                 p["cupo_disponible"], p["periodo"], p["plan_estudios"], p["estatus"],
                 p["creado_por"], p["propuesto_por"], p["motivo_rechazo"], p["validado_por"],
                 p["validado_en"], _fecha(p["creado_en"] if "creado_en" in p.keys() else None)))

    # ------------------------------------------------------------------- planes
    if "planes_servicio" in tablas:
        for p in _filas(vieja, "planes_servicio"):
            cols = p.keys()
            nueva.execute(
                """INSERT INTO planes_servicio (id, nombre, actividades, cronograma,
                       horas_por_periodo, activo, creado_por, creado_en)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (p["id"], p["nombre"], p["actividades"], p["cronograma"],
                 p["horas_por_periodo"], p["activo"] if "activo" in cols else 1,
                 p["creado_por"] if "creado_por" in cols else None,
                 _fecha(p["creado_en"] if "creado_en" in cols else None)))

    # ---------------------------------------------------------------- servicios
    if "servicios_sociales" in tablas:
        for s in _filas(vieja, "servicios_sociales"):
            nueva.execute(
                """INSERT INTO servicios_sociales (id, alumno_id, programa_id, plan_id, estatus,
                       fecha_inicio, fecha_fin, horas_requeridas, creado_en)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (s["id"], s["alumno_id"], s["programa_id"], s["plan_id"], s["estatus"],
                 s["fecha_inicio"], s["fecha_fin"], s["horas_requeridas"],
                 _fecha(s["creado_en"] if "creado_en" in s.keys() else None)))

    if "bajas" in tablas:
        for b in _filas(vieja, "bajas"):
            nueva.execute(
                """INSERT INTO bajas (id, servicio_id, motivo, fecha, registrada_por)
                   VALUES (?, ?, ?, ?, ?)""",
                (b["id"], b["servicio_id"], b["motivo"], b["fecha"], b["registrada_por"]))

    if "registro_horas" in tablas:
        for r in _filas(vieja, "registro_horas"):
            nueva.execute(
                """INSERT INTO registro_horas (id, servicio_id, fecha, horas, registrada_por,
                       creado_en) VALUES (?, ?, ?, ?, ?, ?)""",
                (r["id"], r["servicio_id"], r["fecha"], r["horas"], r["registrada_por"],
                 _fecha(r["creado_en"] if "creado_en" in r.keys() else None)))

    if "periodos_entrega" in tablas:
        columnas_viejas = _columnas(vieja, "periodos_entrega")
        vistos: set[tuple[str, int]] = set()
        for p in _filas(vieja, "periodos_entrega"):
            # Las bases viejas guardaban un periodo por servicio (reportes
            # bimestrales). Ahora la fecha es global para todos los alumnos:
            # se conserva la primera fecha encontrada de cada documento.
            tipo = p["tipo"] if "tipo" in columnas_viejas and p["tipo"] else "REPORTE_BIMESTRAL"
            numero = p["numero_reporte"] or (1 if tipo == "REPORTE_BIMESTRAL" else 0)
            if (tipo, numero) in vistos:
                continue
            vistos.add((tipo, numero))
            nueva.execute(
                """INSERT INTO periodos_entrega (id, tipo, numero_reporte,
                       fecha_inicio, fecha_fin, definido_por)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (p["id"], tipo, numero, p["fecha_inicio"], p["fecha_fin"],
                 p["definido_por"] if "definido_por" in columnas_viejas else None))

    # --------------------------------------------------------------- documentos
    if "documentos" in tablas:
        for d in _filas(vieja, "documentos"):
            nueva.execute(
                """INSERT INTO documentos (id, servicio_id, tipo, numero_reporte, version,
                       estatus, nombre_original, ruta_archivo, tamano_bytes, subido_por,
                       subido_en, revisado_por, revisado_en)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (d["id"], d["servicio_id"], d["tipo"], d["numero_reporte"], d["version"],
                 d["estatus"], d["nombre_original"], d["ruta_archivo"], d["tamano_bytes"],
                 d["subido_por"] if "subido_por" in d.keys() else None,
                 d["subido_en"], d["revisado_por"], d["revisado_en"]))

    if "observaciones" in tablas:
        for o in _filas(vieja, "observaciones"):
            nueva.execute(
                """INSERT INTO observaciones (id, documento_id, autor_id, texto, creada_en)
                   VALUES (?, ?, ?, ?, ?)""",
                (o["id"], o["documento_id"], o["autor_id"], o["texto"], o["creada_en"]))

    if "expediciones" in tablas:
        for e in _filas(vieja, "expediciones"):
            cols = e.keys()
            nueva.execute(
                """INSERT INTO expediciones (id, servicio_id, tipo, generada_por, generada_en,
                       ruta_archivo) VALUES (?, ?, ?, ?, ?, ?)""",
                (e["id"], e["servicio_id"], e["tipo"], e["generada_por"], e["generada_en"],
                 e["ruta_archivo"] if "ruta_archivo" in cols else None))

    if "constancias" in tablas:
        for c in _filas(vieja, "constancias"):
            cols = c.keys()
            nueva.execute(
                """INSERT INTO constancias (id, servicio_id, folio, ruta_archivo, emitida_por,
                       emitida_en) VALUES (?, ?, ?, ?, ?, ?)""",
                (c["id"], c["servicio_id"], c["folio"],
                 c["ruta_archivo"] if "ruta_archivo" in cols else None,
                 c["emitida_por"], c["emitida_en"]))

    if "plantillas_documento" in tablas:
        for p in _filas(vieja, "plantillas_documento"):
            nueva.execute(
                """INSERT INTO plantillas_documento (id, tipo, nombre_original, ruta_archivo,
                       subido_por, subido_en) VALUES (?, ?, ?, ?, ?, ?)""",
                (p["id"], p["tipo"], p["nombre_original"], p["ruta_archivo"],
                 p["subido_por"], p["subido_en"]))

    if "notificaciones" in tablas:
        for n in _filas(vieja, "notificaciones"):
            nueva.execute(
                """INSERT INTO notificaciones (id, usuario_id, mensaje, leida, creada_en)
                   VALUES (?, ?, ?, ?, ?)""",
                (n["id"], n["usuario_id"], n["mensaje"], n["leida"], n["creada_en"]))

    if "bitacora" in tablas:
        for b in _filas(vieja, "bitacora"):
            nueva.execute(
                """INSERT INTO bitacora (id, usuario_id, accion, detalle, fecha)
                   VALUES (?, ?, ?, ?, ?)""",
                (b["id"], b["usuario_id"], b["accion"], b["detalle"], b["fecha"]))

    if "contacto_personal" in tablas:
        for c in _filas(vieja, "contacto_personal"):
            nueva.execute(
                """INSERT INTO contacto_personal (usuario_id, telefono, domicilio,
                       actualizado_en) VALUES (?, ?, ?, ?)""",
                (c["usuario_id"], c["telefono"], c["domicilio"], c["actualizado_en"]))

    if "recuperaciones_password" in tablas:
        for r in _filas(vieja, "recuperaciones_password"):
            nueva.execute(
                """INSERT INTO recuperaciones_password (id, usuario_id, token, expira_en, usado)
                   VALUES (?, ?, ?, ?, ?)""",
                (r["id"], r["usuario_id"], r["token"], r["expira_en"], r["usado"]))

    nueva.commit()
    vieja.close()
    nueva.close()

    # Reemplaza la base original (el respaldo ya existe).
    for sufijo in ("", "-wal", "-shm"):
        Path(str(RUTA_BD) + sufijo).unlink(missing_ok=True)
    RUTA_NUEVA.replace(RUTA_BD)
    print("MigraciÃ³n terminada. Base corregida lista.")


if __name__ == "__main__":
    migrar()

