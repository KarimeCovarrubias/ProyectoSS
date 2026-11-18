"""Archivos subidos: se guardan en SistemaSS/uploads, FUERA de frontend (RNF-01).
Solo se pueden ver a través de rutas protegidas por rol."""
import os
import uuid
from pathlib import Path

# backend/rutas/archivos.py -> parents[2] = SistemaSS
UPLOADS = Path(__file__).resolve().parents[2] / "uploads"


def tamano(archivo):
    """Tamaño en bytes de un archivo recibido (sin consumirlo)."""
    archivo.stream.seek(0, os.SEEK_END)
    total = archivo.stream.tell()
    archivo.stream.seek(0)
    return total


def es_pdf(archivo):
    """Revisa que el contenido sea realmente un PDF, no solo que termine en .pdf."""
    cabecera = archivo.stream.read(5)
    archivo.stream.seek(0)
    return cabecera == b"%PDF-"


def guardar(archivo, subcarpeta, extension=".pdf"):
    """Guarda con un nombre generado (nunca el que manda el usuario).
    Devuelve (ruta_completa, ruta_relativa_para_la_BD)."""
    carpeta = UPLOADS / subcarpeta
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = uuid.uuid4().hex + extension
    destino = carpeta / nombre
    archivo.save(destino)
    return destino, f"{subcarpeta}/{nombre}"


def ruta_segura(relativa):
    """Convierte la ruta guardada en la BD en una ruta real, solo si queda dentro de uploads."""
    if not relativa:
        return None
    destino = (UPLOADS / relativa).resolve()
    if destino != UPLOADS.resolve() and UPLOADS.resolve() not in destino.parents:
        return None
    return destino


def ruta_para_bd(ruta_completa):
    """Ruta relativa (dentro de uploads) para guardar en la base de datos."""
    completa = Path(ruta_completa).resolve()
    return str(completa.relative_to(UPLOADS.resolve())).replace("\\", "/")
