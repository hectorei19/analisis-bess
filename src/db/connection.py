"""
Conexión a la base de datos.

- Si existen las variables de entorno TURSO_URL y TURSO_TOKEN → Turso (libSQL).
- Si no → archivo SQLite local (por defecto data/bess.db; se puede cambiar con
  la variable BESS_DB_PATH).

Ambas conexiones siguen la interfaz DB-API de Python (execute, executemany,
commit...), así que el resto del código no necesita saber cuál se usa.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from src.db.schema import create_tables

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "bess.db"


def get_connection(db_path: str | Path | None = None):
    """Abre la conexión (Turso o SQLite) y se asegura de que existan las tablas."""
    turso_url = os.getenv("TURSO_URL")
    turso_token = os.getenv("TURSO_TOKEN")

    if db_path is None and turso_url and turso_token:
        try:
            import libsql  # se instalará cuando pasemos a Turso
        except ImportError as exc:
            raise RuntimeError(
                "TURSO_URL y TURSO_TOKEN están definidos, pero falta la librería "
                "'libsql'. Instálala con: pip install libsql"
            ) from exc
        conn = libsql.connect(database=turso_url, auth_token=turso_token)
    else:
        path = Path(db_path or os.getenv("BESS_DB_PATH") or DEFAULT_DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)

    create_tables(conn)
    return conn
