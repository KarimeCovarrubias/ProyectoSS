"""Validaciones reutilizables (reglas del ERS).
Cada función devuelve un mensaje de error, o None si todo está bien."""
import re
import secrets
from datetime import date

DOMINIO_CORREO = "@culiacan.tecnm.mx"
MIN_PORCENTAJE_CREDITOS = 70       # RF-01
MIN_SEMESTRE = 7                   # RF-01
MAX_BYTES_PDF = 5 * 1024 * 1024    # RF-07: 5 MB

# AJUSTA este valor: total de créditos de la carrera según el plan de tu escuela.
CREDITOS_TOTALES_CARRERA = 260


def unir_nombre(nombre, apellido_paterno, apellido_materno=""):
    """Nombre completo para mostrar: 'Juan Pérez López'."""
    partes = [nombre, apellido_paterno, apellido_materno]
    return " ".join(p.strip() for p in partes if p and p.strip())


def validar_nombres(nombre, apellido_paterno, apellido_materno=None):
    """Toda persona debe tener nombre y los dos apellidos (requisito del sistema)."""
    if not str(nombre or "").strip():
        return "El nombre es obligatorio"
    if not str(apellido_paterno or "").strip():
        return "El apellido paterno es obligatorio"
    if apellido_materno is None or not str(apellido_materno).strip():
        return "El apellido materno es obligatorio"
    for valor, campo in ((nombre, "nombre"), (apellido_paterno, "apellido paterno"),
                         (apellido_materno, "apellido materno")):
        if len(str(valor).strip()) > 80:
            return f"El {campo} no puede pasar de 80 caracteres"
        if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]+", str(valor).strip()):
            return f"El {campo} contiene caracteres no válidos"
    return None


def validar_password(password):
    """RF-01 / RF-02: 10 caracteres, al menos una mayúscula y un número."""
    if len(password) < 10:
        return "La contraseña debe tener al menos 10 caracteres"
    if not any(c.isupper() for c in password):
        return "La contraseña debe tener al menos una mayúscula"
    if not any(c.isdigit() for c in password):
        return "La contraseña debe tener al menos un número"
    return None


def generar_password():
    """Contraseña inicial aleatoria que cumple las reglas (12 caracteres)."""
    mayus = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    minus = "abcdefghijkmnpqrstuvwxyz"
    nums = "23456789"
    todos = mayus + minus + nums
    car = [secrets.choice(mayus), secrets.choice(nums)]
    car += [secrets.choice(todos) for _ in range(10)]
    secrets.SystemRandom().shuffle(car)
    return "".join(car)


def validar_correo_institucional(correo):
    """El correo debe terminar en @culiacan.tecnm.mx."""
    patron = r"[a-z0-9._-]+" + re.escape(DOMINIO_CORREO)
    if not re.fullmatch(patron, str(correo or "").strip().lower()):
        return f"El correo debe ser institucional y terminar en {DOMINIO_CORREO}"
    return None


def validar_numero_control(numero_control):
    """RF-01: exactamente 8 dígitos."""
    if not re.fullmatch(r"[0-9]{8}", str(numero_control or "")):
        return "El número de control debe tener exactamente 8 dígitos"
    return None


def correo_de_alumno(numero_control):
    """RF-01: el correo del alumno es su número de control + dominio del Tec."""
    return numero_control + DOMINIO_CORREO


def validar_curp(curp):
    patron = r"[A-Z]{4}[0-9]{6}[HMX][A-Z]{2}[A-Z]{3}[A-Z0-9][0-9]"
    if not re.fullmatch(patron, str(curp or "").strip().upper()):
        return "La CURP no es válida (18 caracteres)"
    return None


def validar_telefono(telefono):
    if not re.fullmatch(r"[0-9]{10}", str(telefono or "")):
        return "El teléfono debe tener 10 dígitos"
    return None


def validar_semestre(semestre):
    """RF-01: 7.º semestre o más."""
    if int(semestre) < MIN_SEMESTRE:
        return f"El alumno debe cursar el semestre {MIN_SEMESTRE} o superior"
    return None


def calcular_porcentaje_creditos(creditos, total=CREDITOS_TOTALES_CARRERA):
    return round(int(creditos) * 100 / total, 2)


def validar_creditos(creditos, total=CREDITOS_TOTALES_CARRERA):
    """RF-01: al menos 70 % de los créditos."""
    porcentaje = calcular_porcentaje_creditos(creditos, total)
    if porcentaje < MIN_PORCENTAJE_CREDITOS:
        return (f"Créditos insuficientes: lleva {porcentaje} % y se requiere "
                f"al menos {MIN_PORCENTAJE_CREDITOS} %")
    if porcentaje > 100:
        return "Los créditos acumulados no pueden superar el total de la carrera"
    return None


def validar_pdf(nombre_archivo, tamano_bytes):
    """RF-07: solo .pdf y máximo 5 MB."""
    if not str(nombre_archivo or "").lower().endswith(".pdf"):
        return "Archivo no válido: solo se aceptan archivos .pdf"
    if tamano_bytes is None or tamano_bytes <= 0:
        return "Archivo no válido: el archivo está vacío"
    if tamano_bytes > MAX_BYTES_PDF:
        return "Archivo no válido: el tamaño máximo es 5 MB"
    return None


def validar_fecha(texto, nombre="fecha"):
    try:
        date.fromisoformat(str(texto))
        return None
    except (TypeError, ValueError):
        return f"La {nombre} no es válida (use AAAA-MM-DD)"


def validar_periodo(periodo):
    """Periodo con formato AAAA-N, por ejemplo 2026-2."""
    if not re.fullmatch(r"\d{4}-[1-3]", str(periodo or "").strip()):
        return "El periodo debe tener el formato AAAA-N (ej. 2026-2)"
    return None


def validar_entero_positivo(valor, campo, maximo=10000):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return f"{campo} debe ser un número entero positivo"
    if numero <= 0:
        return f"{campo} debe ser un número entero positivo"
    if numero > maximo:
        return f"{campo} no puede ser mayor que {maximo}"
    return None


def validar_plan(plan):
    if plan not in ("NUEVO", "ANTIGUO", "AMBOS"):
        return "Plan de estudios no válido"
    return None


def validar_origen(origen):
    if origen not in ("INTERNA", "EXTERNA"):
        return "Indique si el programa es interno o externo (fuera de la escuela)"
    return None
