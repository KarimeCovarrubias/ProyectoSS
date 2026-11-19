# Conexión y manejo de transacciones con la base de datos SQLite
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUTA_BD = BASE / "servicio_social.db"
RUTA_SCHEMA = BASE / "schema.sql"


def conectar():
    
    con = sqlite3.connect(RUTA_BD, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


@contextmanager
def transaccion():
    
    con = conectar()
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def registrar_bitacora(con, usuario_id, accion, detalle=None):

    con.execute(
        "INSERT INTO bitacora (usuario_id, accion, detalle) VALUES (?, ?, ?)",
        (usuario_id, accion, detalle))


def crear_tablas():

    for sufijo in ("", "-wal", "-shm"):
        Path(str(RUTA_BD) + sufijo).unlink(missing_ok=True)
    con = conectar()
    con.executescript(RUTA_SCHEMA.read_text(encoding="utf-8"))
    con.commit()
    con.close()