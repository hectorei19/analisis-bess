"""
Calcula la tabla `bess_daily` a partir de los precios ES guardados.

Uso (desde la carpeta del proyecto):
    .\\.venv\\Scripts\\python.exe -m scripts.compute_bess_daily
    .\\.venv\\Scripts\\python.exe -m scripts.compute_bess_daily --start 2026-09-01 --end 2026-09-29

Duraciones 1, 2 y 4 h, rte 0,88, 1 ciclo/día, métodos óptimo y simple.
Repetirlo no duplica filas (se actualizan).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta

import pandas as pd

from src.analytics.bess_daily import compute_bess_daily
from src.db.connection import get_connection
from src.db.repository import load_prices, save_bess_daily
from src.ingest.omie import TZ_MARKET


def _local_midnight_utc(d: date) -> pd.Timestamp:
    return pd.Timestamp(d).tz_localize(TZ_MARKET).tz_convert("UTC")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Calcula bess_daily")
    ap.add_argument("--start", type=date.fromisoformat, help="primer día (incluido)")
    ap.add_argument("--end", type=date.fromisoformat, help="último día (incluido)")
    args = ap.parse_args(argv)

    conn = get_connection()
    prices = load_prices(
        conn, "ES",
        start_utc=_local_midnight_utc(args.start) if args.start else None,
        end_utc=_local_midnight_utc(args.end + timedelta(days=1)) if args.end else None,
    )
    if prices.empty:
        print("No hay precios ES en la base de datos. Ejecuta antes scripts.backfill_prices")
        return 1

    t0 = time.time()
    daily = compute_bess_daily(prices)
    n = save_bess_daily(conn, daily)
    print(f"bess_daily: {n} filas guardadas ({daily['date'].nunique()} días) "
          f"en {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
