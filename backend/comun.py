# Funciones compartidas para notificaciones, conteo de horas y control de documentos
from datetime import date

# Nombre completo de la tabla usuarios
NOMBRE_SQL = ("trim(u.nombre || ' ' || u.apellido_paterno || ' ' || "
              "coalesce(nullif(u.apellido_materno, ''), ''))")

# Nombre completo del titular de una empresa 
TITULAR_SQL = "trim(e.titular_nombre || ' ' || e.titular_apellido_paterno || ' ' || e.titular_apellido_materno)"

ESTATUS_VIGENTE = ("PENDIENTE", "ACTIVO")
ESTATUS_TERMINADO = ("CONCLUIDO", "LIBERADO")

# Las horas se acumulan por reporte bimestral VALIDADO.
HORAS_POR_REPORTE = 160
REPORTES_BIMESTRALES = 3


def nombre_completo(nombre, paterno, materno=""):
    return " ".join(p.strip() for p in (nombre, paterno, materno) if p and p.strip())


def notificar(con, usuario_id, mensaje):

    if usuario_id:
        con.execute("INSERT INTO notificaciones (usuario_id, mensaje) VALUES (?, ?)",
                    (usuario_id, mensaje))


def notificar_rol(con, rol, mensaje):

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


def reportes_validados(con, servicio_id):
    
    fila = con.execute(
        "SELECT COUNT(DISTINCT numero_reporte) FROM documentos "
        "WHERE servicio_id = ? AND tipo = 'REPORTE_BIMESTRAL' AND estatus = 'VALIDADO'",
        (servicio_id,)).fetchone()
    return int(fila[0] or 0)


def horas_acumuladas(con, servicio_id):
   
    servicio = con.execute("SELECT horas_requeridas FROM servicios_sociales WHERE id = ?",
                           (servicio_id,)).fetchone()
    requeridas = int(servicio["horas_requeridas"] or 0) if servicio else 0
    acumuladas = reportes_validados(con, servicio_id) * HORAS_POR_REPORTE
    return min(acumuladas, requeridas) if requeridas else acumuladas


def avance_horas(con, servicio):
    requeridas = int(servicio["horas_requeridas"] or 0)
    reportes = reportes_validados(con, servicio["id"])
    acumuladas = horas_acumuladas(con, servicio["id"])
    porcentaje = round(min(100.0, acumuladas * 100.0 / requeridas), 2) if requeridas else 0.0
    return {
        "horas_requeridas": requeridas,
        "horas_acumuladas": acumuladas,
        "horas_restantes": max(0, requeridas - acumuladas),
        "porcentaje_avance": porcentaje,
        # Detalle para el apartado del alumno: horas por reporte validado.
        "horas_por_reporte": HORAS_POR_REPORTE,
        "reportes_validados": reportes,
        "reportes_requeridos": REPORTES_BIMESTRALES,
    }


def documentos_requeridos(con, servicio_id, incluir_carta_terminacion=False):
 
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


def carta_terminacion(con, servicio_id):

    return con.execute(
        "SELECT d.id, d.nombre_original, d.ruta_archivo, d.subido_en "
        "FROM documentos d JOIN usuarios u ON u.id = d.subido_por "
        "WHERE d.servicio_id = ? AND d.tipo = 'CARTA_TERMINACION' "
        "AND d.estatus = 'VALIDADO' AND u.rol = 'JEFE_VINCULACION' "
        "ORDER BY d.id DESC LIMIT 1", (servicio_id,)).fetchone()


def carta_firmada_alumno(con, servicio_id, alumno_id):

    return con.execute(
        "SELECT id, version, nombre_original, ruta_archivo, estatus, subido_en, revisado_en "
        "FROM documentos WHERE servicio_id = ? AND tipo = 'CARTA_TERMINACION' "
        "AND subido_por = ? AND estatus <> 'REEMPLAZADO' "
        "ORDER BY version DESC, id DESC LIMIT 1",
        (servicio_id, alumno_id)).fetchone()


def listo_para_carta(con, servicio_id):
   
    servicio = con.execute(
        "SELECT estatus, horas_requeridas FROM servicios_sociales WHERE id = ?",
        (servicio_id,)).fetchone()
    if not servicio or servicio["estatus"] == "BAJA":
        return False
    if horas_acumuladas(con, servicio_id) < int(servicio["horas_requeridas"] or 0):
        return False
    return not documentos_faltantes(con, servicio_id)


def carta_terminacion_habilitada(con, servicio_id):

    if not listo_para_carta(con, servicio_id):
        return None
    return carta_terminacion(con, servicio_id)


def periodo_entrega(con, tipo, numero_reporte=0):

    return con.execute(
        "SELECT fecha_inicio, fecha_fin FROM periodos_entrega "
        "WHERE tipo = ? AND numero_reporte = ?",
        (tipo, numero_reporte)).fetchone()


def estado_periodo(con, tipo, numero_reporte=0, hoy=None):
    
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
   
    servicio = con.execute("SELECT * FROM servicios_sociales WHERE id = ?",
                           (servicio_id,)).fetchone()
    if not servicio or servicio["estatus"] not in ("PENDIENTE", "ACTIVO"):
        return False
    if not listo_para_carta(con, servicio_id):
        return False
    con.execute("UPDATE servicios_sociales SET estatus = 'CONCLUIDO', "
                "actualizado_en = datetime('now') WHERE id = ?", (servicio_id,))
    notificar(con, servicio["alumno_id"],
              "Su servicio social concluyó: horas completas y documentos validados. "
              "El Jefe de Vinculación ya puede subir su carta de terminación en Word.")
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
