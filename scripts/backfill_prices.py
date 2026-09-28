"""
Carga histórica de precios del mercado diario de OMIE en la tabla `prices`.

Uso (desde la carpeta del proyecto):
    .\\.venv\\Scripts\\python.exe -m scripts.backfill_prices --start 2025-09-28 --end 2026-09-29

Sin parámetros carga el último año hasta mañana (OMIE publica el día D+1
hacia las 13:00). Los ficheros originales se guardan en data/raw/omie y se
reutilizan: repetir el comando no vuelve a descargar lo que ya existe.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

import requests

from src.db.connection import PROJECT_ROOT, get_connection
from src.db.repository import save_prices
from src.ingest.omie import load_day

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "omie"


def parse_args(argv=None):
    today = date.today()
    ap = argparse.ArgumentParser(description="Backfill de precios OMIE")
    ap.add_argument("--start", type=date.fromisoformat, default=today - timedelta(days=365),
                    help="primer día (AAAA-MM-DD), incluido")
    ap.add_argument("--end", type=date.fromisoformat, default=today + timedelta(days=1),
                    help="último día (AAAA-MM-DD), incluido")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.end < args.start:
        print("Error: --end es anterior a --start")
        return 2

    conn = get_connection()
    session = requests.Session()
    today = date.today()
    saved_days, missing = 0, []

    day = args.start
    total = (args.end - args.start).days + 1
    while day <= args.end:
        df = load_day(day, raw_dir=RAW_DIR, session=session)
        if df is None:
            if day <= today:
                missing.append(day)            # debería existir: se avisa, no se inventa
            print(f"{day}  no publicado en OMIE")
        else:
            save_prices(conn, df)
            saved_days += 1
            n = int((df["market"] == "ES").sum())
            print(f"{day}  {n:3d} periodos  ({saved_days}/{total})")
        day += timedelta(days=1)

    print(f"\nDías guardados: {saved_days} de {total}")
    if missing:
        print("ATENCIÓN: días pasados sin fichero en OMIE:", ", ".join(map(str, missing)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
