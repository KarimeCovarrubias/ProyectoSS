"""Generación de formatos Word (.docx) editables (RF-06, CU12).

Si el Jefe de Oficina de SS subió una plantilla para el tipo de documento, se usa
esa plantilla y se sustituyen los marcadores {{...}}. Si no hay plantilla, se
genera un documento con los datos del alumno y de su programa.
"""
from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

TITULOS = {
    "CARTA_PRESENTACION": "Carta de presentación",
    "SOLICITUD": "Solicitud de servicio social",
    "CARTA_ACEPTACION": "Carta de aceptación",
    "REPORTE_BIMESTRAL": "Reporte bimestral de actividades",
    "MEMORIA_FINAL": "Memoria final del servicio social",
    "CARTA_TERMINACION": "Carta de terminación del servicio social",
    "CONSTANCIA": "Constancia de terminación del servicio social",
}


def _reemplazar_en_parrafo(parrafo, datos):
    for run in parrafo.runs:
        texto = run.text
        for clave, valor in datos.items():
            texto = texto.replace("{{" + clave + "}}", str(valor or ""))
        run.text = texto


def _aplicar_plantilla(contenido, datos):
    documento = Document(io.BytesIO(contenido))
    for parrafo in documento.paragraphs:
        _reemplazar_en_parrafo(parrafo, datos)
    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                for parrafo in celda.paragraphs:
                    _reemplazar_en_parrafo(parrafo, datos)
    for seccion in documento.sections:
        for parrafo in seccion.header.paragraphs + seccion.footer.paragraphs:
            _reemplazar_en_parrafo(parrafo, datos)
    return documento


def _parrafo(documento, texto, negritas=False, centrado=False, tamano=None):
    p = documento.add_paragraph()
    run = p.add_run(texto)
    run.bold = negritas
    if tamano:
        run.font.size = Pt(tamano)
    if centrado:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def _generar_simple(tipo, d):
    documento = Document()
    estilo = documento.styles["Normal"]
    estilo.font.name = "Arial"
    estilo.font.size = Pt(11)

    _parrafo(documento, "INSTITUTO TECNOLÓGICO DE CULIACÁN", True, True, 14)
    _parrafo(documento, "Departamento de Gestión Tecnológica y Vinculación", False, True, 10)
    _parrafo(documento, "Oficina de Servicio Social y Desarrollo Comunitario", False, True, 10)
    documento.add_paragraph()
    _parrafo(documento, TITULOS.get(tipo, tipo).upper(), True, True, 13)
    documento.add_paragraph()

    if tipo == "CONSTANCIA":
        _parrafo(documento, f"Folio: {d.get('folio', '')}", False, False)
        documento.add_paragraph()
        _parrafo(documento,
                 "Se hace constar que el(la) alumno(a) "
                 f"{d.get('alumno_nombre', '')}, con número de control "
                 f"{d.get('control', '')}, de la carrera de {d.get('carrera', '')}, "
                 "concluyó satisfactoriamente su Servicio Social cumpliendo "
                 f"{d.get('horas_acumuladas', '')} de {d.get('horas_requeridas', '')} horas "
                 "requeridas, en el programa "
                 f"\"{d.get('programa', '')}\" de la dependencia "
                 f"\"{d.get('dependencia', '')}\", durante el periodo "
                 f"{d.get('periodo', '')}.")
        documento.add_paragraph()
        _parrafo(documento, "Para los fines que al interesado convengan, se expide la presente.")
    else:
        _parrafo(documento, f"Nombre del alumno: {d.get('alumno_nombre', '')}")
        _parrafo(documento, f"Número de control: {d.get('control', '')}")
        _parrafo(documento, f"Carrera: {d.get('carrera', '')}")
        _parrafo(documento, f"Semestre: {d.get('semestre', '')}")
        _parrafo(documento, f"Plan de servicio social: {d.get('plan', '')}")
        _parrafo(documento, f"Programa: {d.get('programa', '')}")
        _parrafo(documento, f"Dependencia receptora: {d.get('dependencia', '')}")
        _parrafo(documento, f"Responsable: {d.get('responsable', '')}")
        _parrafo(documento, f"Domicilio: {d.get('domicilio', '')}")
        _parrafo(documento, f"Teléfono: {d.get('telefono', '')}")
        _parrafo(documento, f"Periodo: {d.get('periodo', '')}")
        _parrafo(documento, f"Horas: {d.get('horas', '')}")
        documento.add_paragraph()
        _parrafo(documento, "Actividades:", True)
        _parrafo(documento, d.get("actividades", ""))
        if tipo == "REPORTE_BIMESTRAL":
            documento.add_paragraph()
            _parrafo(documento, f"Reporte bimestral número: {d.get('numero_reporte', '')}", True)
            _parrafo(documento, "Actividades realizadas en el periodo:")
            documento.add_paragraph("")
            documento.add_paragraph("")

    documento.add_paragraph()
    documento.add_paragraph()
    _parrafo(documento, "_________________________________________", False, True)
    _parrafo(documento, d.get("firmante", "Responsable del programa"), False, True)
    _parrafo(documento, f"{d.get('lugar_fecha', '')}", False, True)
    return documento


def generar_docx(tipo, datos, plantilla_bytes=None):
    """Devuelve el contenido binario del .docx."""
    datos = {k: v for k, v in datos.items() if v is not None}
    datos.setdefault("fecha", date.today().strftime("%d/%m/%Y"))
    if plantilla_bytes:
        documento = _aplicar_plantilla(plantilla_bytes, datos)
    else:
        documento = _generar_simple(tipo, datos)
    salida = io.BytesIO()
    documento.save(salida)
    return salida.getvalue()
