"""
Copia de los precios en un archivo comprimido dentro del repositorio
(snapshot/prices.csv.gz). Sirve para que la web publicada tenga datos sin
depender de la base de datos local: al arrancar, si la tabla `prices` está
vacía, se rellena desde este archivo.

Regenerar tras actualizar precios:
    .\\.venv\\Scripts\\python.exe -m scripts.export_snapshot
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.db.connection import PROJECT_ROOT
from src.db.repository import PRICE_COLUMNS, TS_FORMAT, load_prices, save_prices

SNAPSHOT_PATH = PROJECT_ROOT / "snapshot" / "prices.csv.gz"
MARKETS = ("ES", "PT")


def export_snapshot(conn, path: Path = SNAPSHOT_PATH) -> int:
    frames = [load_prices(conn, m) for m in MARKETS]
    df = pd.concat(frames, ignore_index=True)[PRICE_COLUMNS]
    df["ts_utc"] = df["ts_utc"].dt.strftime(TS_FORMAT)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
    return len(df)


def load_snapshot(conn, path: Path = SNAPSHOT_PATH) -> int:
    df = pd.read_csv(path)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], format=TS_FORMAT, utc=True)
    return save_prices(conn, df)


def seed_if_empty(conn, path: Path = SNAPSHOT_PATH) -> int:
    """Rellena `prices` desde el archivo si la tabla está vacía. Devuelve filas cargadas."""
    has_rows = conn.execute("SELECT 1 FROM prices LIMIT 1").fetchone()
    if has_rows or not path.exists():
        return 0
    return load_snapshot(conn, path)
