"""Crea la base de datos VACÍA y el acceso del primer (y único) Administrador.
Todos los demás usuarios los crea el Administrador desde el sistema (CU02).

Uso (desde la carpeta SistemaSS):  python crear_bd.py
(Borra la base existente y la crea de nuevo.)"""
from getpass import getpass

from werkzeug.security import generate_password_hash

from backend.db import conectar, crear_tablas
from backend.validaciones import (validar_correo_institucional, validar_nombres,
                                  validar_password)

print("=== Crear base de datos y Administrador del Sistema ===")
print("ATENCIÓN: si ya existe una base de datos, se BORRARÁ.")
if input("¿Continuar? (s/n): ").strip().lower() != "s":
    raise SystemExit("Cancelado.")

identificador = input("Número de empleado del administrador: ").strip()
nombre = input("Nombre(s): ").strip()
apellido_paterno = input("Apellido paterno: ").strip()
apellido_materno = input("Apellido materno: ").strip()
correo = input("Correo institucional (@culiacan.tecnm.mx): ").strip().lower()
password = getpass("Contraseña (10+ caracteres, 1 mayúscula, 1 número): ")

if not identificador:
    raise SystemExit("El número de empleado es obligatorio.")
error = (validar_nombres(nombre, apellido_paterno, apellido_materno)
         or validar_correo_institucional(correo) or validar_password(password))
if error:
    raise SystemExit(error)

crear_tablas()
con = conectar()
con.execute(
    "INSERT INTO usuarios (identificador, nombre, apellido_paterno, apellido_materno, "
    "correo, password_hash, rol) VALUES (?, ?, ?, ?, ?, ?, 'ADMINISTRADOR')",
    (identificador, nombre, apellido_paterno, apellido_materno, correo,
     generate_password_hash(password)))
con.commit()
con.close()
print("Listo: base de datos creada con el administrador. Ya puedes iniciar sesión.")
