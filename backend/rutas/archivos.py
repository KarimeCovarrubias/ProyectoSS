# Manejo y subida de archivos del sistema
# Se guardan en una carpeta privada  para que nadie acceda directo por URL sin permisos
import os
import uuid
from pathlib import Path

# Ruta base a la carpeta uploads en la raíz del proyecto
UPLOADS = Path(__file__).resolve().parents[2] / "uploads"

# Mide el tamaño del archivo en bytes y regresa el puntero al inicio para poder leerlo después
def tamano(archivo):
    archivo.stream.seek(0, os.SEEK_END)
    total = archivo.stream.tell()
    archivo.stream.seek(0)
    return total

# Revisa la cabecera para asegurar que sea un PDF real y no solo la extensión cambiada
def es_pdf(archivo):
    cabecera = archivo.stream.read(5)
    archivo.stream.seek(0)
    return cabecera == b"%PDF-"

# Guarda el archivo con un UUID para no sobreescribir archivos ni guardar nombres con caracteres raros
def guardar(archivo, subcarpeta, extension=".pdf"):
    carpeta = UPLOADS / subcarpeta
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = uuid.uuid4().hex + extension
    destino = carpeta / nombre
    archivo.save(destino)
    return destino, f"{subcarpeta}/{nombre}"

# Valida que la ruta no intente salirse de la carpeta
def ruta_segura(relativa):
    if not relativa:
        return None
    destino = (UPLOADS / relativa).resolve()
    if destino != UPLOADS.resolve() and UPLOADS.resolve() not in destino.parents:
        return None
    return destino

# Convierte la ruta absoluta en una ruta relativa limpia con '/' para guardarla en la base de datos
def ruta_para_bd(ruta_completa):
    completa = Path(ruta_completa).resolve()
    return str(completa.relative_to(UPLOADS.resolve())).replace("\\", "/")
