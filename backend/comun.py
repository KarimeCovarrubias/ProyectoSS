"""Utilidades compartidas por las rutas (nombres, notificaciones, avance, documentos)."""
from datetime import date

# Nombre completo de la tabla usuarios (alias u)
NOMBRE_SQL = ("trim(u.nombre || ' ' || u.apellido_paterno || ' ' || "
              "coalesce(nullif(u.apellido_materno, ''), ''))")

# Nombre completo del titular de una empresa (alias e)
TITULAR_SQL = "trim(e.titular_nombre || ' ' || e.titular_apellido_paterno || ' ' || e.titular_apellido_materno)"

ESTATUS_VIGENTE = ("PENDIENTE", "ACTIVO")
ESTATUS_TERMINADO = ("CONCLUIDO", "LIBERADO")


def nombre_completo(nombre, paterno, materno=""):
    return " ".join(p.strip() for p in (nombre, paterno, materno) if p and p.strip())


def notificar(con, usuario_id, mensaje):
    """Crea una notificación para un usuario (RF-05, RF-07, RF-11, RF-14..16)."""
    if usuario_id:
        con.execute("INSERT INTO notificaciones (usuario_id, mensaje) VALUES (?, ?)",
                    (usuario_id, mensaje))


def notificar_rol(con, rol, mensaje):
    """Notifica a todos los usuarios activos de un rol (p. ej. a la Oficina de SS)."""
    for fila in con.execute("SELECT id FROM usuarios WHERE rol = ? AND activo = 1", (rol,)):
        notificar(con, fila["id"], mensaje)


def servicio_del_alumno(con, alumno_id, incluir_vigente=True):
    estatus = ESTATUS_VIGENTE if incluir_vigente else ESTATUS_TERMINADO
    marcas = ", ".join("?" for _ in estatus)
    return con.execute(
        f"SELECT * FROM servicios_sociales WHERE alumno_id = ? AND estatus IN ({marcas}) "
        "ORDER BY id DESC LIMIT 1", (alumno_id, *estatus)).fetchone()


def servicio_activo(con, alumno_id):
    return con.execute(
        "SELECT * FROM servicios_sociales WHERE alumno_id = ? "
        "AND estatus IN ('PENDIENTE','ACTIVO') ORDER BY id DESC LIMIT 1",
        (alumno_id,)).fetchone()


def horas_acumuladas(con, servicio_id):
    fila = con.execute("SELECT COALESCE(SUM(horas), 0) FROM registro_horas WHERE servicio_id = ?",
                       (servicio_id,)).fetchone()
    return int(fila[0] or 0)


def avance_horas(con, servicio):
    requeridas = int(servicio["horas_requeridas"] or 0)
    acumuladas = horas_acumuladas(con, servicio["id"])
    porcentaje = round(min(100.0, acumuladas * 100.0 / requeridas), 2) if requeridas else 0.0
    return {
        "horas_requeridas": requeridas,
        "horas_acumuladas": acumuladas,
        "horas_restantes": max(0, requeridas - acumuladas),
        "porcentaje_avance": porcentaje,
    }


def documentos_requeridos(con, servicio_id, incluir_carta_terminacion=True):
    """Lista de (tipo, numero_reporte) que debe entregar el alumno (CU07)."""
    externo = con.execute(
        "SELECT 1 FROM servicios_sociales ss JOIN programas p ON ss.programa_id = p.id "
        "WHERE ss.id = ? AND p.origen = 'EXTERNA'", (servicio_id,)).fetchone() is not None
    requeridos = [("SOLICITUD", 0), ("CARTA_ACEPTACION", 0),
                  ("REPORTE_BIMESTRAL", 1), ("REPORTE_BIMESTRAL", 2),
                  ("REPORTE_BIMESTRAL", 3), ("MEMORIA_FINAL", 0)]
    if incluir_carta_terminacion:
        requeridos.append(("CARTA_TERMINACION", 0))
    if externo:
        requeridos.insert(0, ("CARTA_PRESENTACION", 0))
    return requeridos


def documento_vigente(con, servicio_id, tipo, numero_reporte=0):
    return con.execute(
        "SELECT * FROM documentos WHERE servicio_id = ? AND tipo = ? AND numero_reporte = ? "
        "AND estatus <> 'REEMPLAZADO' ORDER BY version DESC, id DESC LIMIT 1",
        (servicio_id, tipo, numero_reporte)).fetchone()


def periodo_entrega(con, tipo, numero_reporte=0):
    """Ventana de entrega GLOBAL que definió el Jefe (aplica a todos los alumnos)."""
    return con.execute(
        "SELECT fecha_inicio, fecha_fin FROM periodos_entrega "
        "WHERE tipo = ? AND numero_reporte = ?",
        (tipo, numero_reporte)).fetchone()


def estado_periodo(con, tipo, numero_reporte=0, hoy=None):
    """Indica si el alumno puede subir hoy ese documento (RF-09).

    La fecha es la misma para todos los alumnos. Devuelve
    ``fecha_inicio``/``fecha_fin`` (o None), ``abierto`` y ``motivo``:
    ``SIN_PERIODO``, ``NO_INICIADO`` o ``VENCIDO`` (None cuando está abierto).
    """
    referencia = (hoy or date.today()).isoformat()
    fila = periodo_entrega(con, tipo, numero_reporte)
    if fila is None:
        return {"fecha_inicio": None, "fecha_fin": None, "abierto": False,
                "motivo": "SIN_PERIODO"}
    inicio, fin = fila["fecha_inicio"], fila["fecha_fin"]
    if referencia < inicio:
        motivo = "NO_INICIADO"
    elif referencia > fin:
        motivo = "VENCIDO"
    else:
        motivo = None
    return {"fecha_inicio": inicio, "fecha_fin": fin, "abierto": motivo is None,
            "motivo": motivo}


def documentos_faltantes(con, servicio_id):
    faltantes = []
    for tipo, numero in documentos_requeridos(con, servicio_id):
        doc = documento_vigente(con, servicio_id, tipo, numero)
        if not doc or doc["estatus"] != "VALIDADO":
            faltantes.append({"tipo": tipo, "numero_reporte": numero,
                              "estatus": doc["estatus"] if doc else "SIN_SUBIR"})
    return faltantes


def quizas_concluir(con, servicio_id):
    """Pasa a CONCLUIDO cuando ya están las horas y todos los documentos validados."""
    servicio = con.execute("SELECT * FROM servicios_sociales WHERE id = ?",
                           (servicio_id,)).fetchone()
    if not servicio or servicio["estatus"] != "ACTIVO":
        return False
    if horas_acumuladas(con, servicio_id) < servicio["horas_requeridas"]:
        return False
    if documentos_faltantes(con, servicio_id):
        return False
    con.execute("UPDATE servicios_sociales SET estatus = 'CONCLUIDO', "
                "actualizado_en = datetime('now') WHERE id = ?", (servicio_id,))
    notificar(con, servicio["alumno_id"],
              "Su servicio social concluyó: horas completas y documentos validados. "
              "El Jefe de Vinculación puede emitir su constancia.")
    return True


def liberar_cupo(con, programa_id):
    con.execute("UPDATE programas SET cupo_disponible = MIN(cupo, cupo_disponible + 1), "
                "actualizado_en = datetime('now') WHERE id = ?", (programa_id,))


def hoy():
    return date.today().isoformat()


def fecha_valida(texto):
    try:
        date.fromisoformat(str(texto))
        return True
    except (TypeError, ValueError):
        return False
