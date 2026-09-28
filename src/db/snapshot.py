"""
Copia de los precios en un archivo comprimido dentro del repositorio
(snapshot/prices.csv.gz). Sirve para que la web publicada tenga datos sin
depender de la base de datos local: al arrancar, si el archivo trae más
datos que la tabla `prices` (base vacía o archivo actualizado), se cargan.

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


def sync_from_snapshot(conn, path: Path = SNAPSHOT_PATH) -> int:
    """
    Carga el archivo en `prices` si trae más filas que la base de datos (base
    vacía, o archivo actualizado con días nuevos). Devuelve filas cargadas.
    Una base local con más datos que el archivo no se toca.
    """
    if not path.exists():
        return 0
    n_db = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    df = pd.read_csv(path)
    if len(df) <= n_db:
        return 0
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], format=TS_FORMAT, utc=True)
    return save_prices(conn, df)
