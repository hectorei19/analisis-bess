"""
Precios marginales del mercado diario de OMIE (ficheros marginalpdbc).

Formato verificado (manual OMIE "Modelo de ficheros para la distribución
pública de información", v1.36, apartado 6.18, y ficheros reales):

    MARGINALPDBC;
    2025;10;01;1;105.1;105.1;      ← año;mes;día;periodo;precio PT;precio ES;
    ...
    *

- Hasta el 30-09-2025: periodos horarios (23/24/25 al día).
- Desde el 01-10-2025: periodos de 15 minutos (92/96/100 al día).
- El periodo 1 empieza a las 00:00 hora peninsular española y los periodos son
  consecutivos en tiempo real (en el cambio de hora hay 1 h de menos o de más).
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

URL_TEMPLATE = (
    "https://www.omie.es/es/file-download"
    "?parents=marginalpdbc&filename=marginalpdbc_{yyyymmdd}.1"
)
SOURCE_PREFIX = "OMIE marginalpdbc"
TZ_MARKET = "Europe/Madrid"
MARKETS = {"PT": 1, "ES": 2}          # posición en cada registro (periodo, PT, ES)
USER_AGENT = "BESS-analytics/0.1 (analisis de mercado)"


class OmieFormatError(ValueError):
    """El fichero no tiene el formato esperado: mejor parar que guardar datos dudosos."""


def file_name(day: date) -> str:
    return f"marginalpdbc_{day:%Y%m%d}.1"


def day_length_hours(day: date) -> int:
    """Horas reales del día en Madrid: 23 (marzo), 25 (octubre) o 24."""
    start = pd.Timestamp(day).tz_localize(TZ_MARKET)
    end = pd.Timestamp(day + timedelta(days=1)).tz_localize(TZ_MARKET)
    return int((end - start).total_seconds() // 3600)


def parse_marginalpdbc(text: str, day: date, source: str) -> pd.DataFrame:
    """
    Convierte el contenido de un fichero marginalpdbc en filas de la tabla
    `prices` (una por periodo y mercado), con `ts_utc` = inicio del periodo en UTC.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines or lines[0] != "MARGINALPDBC;" or lines[-1] != "*":
        raise OmieFormatError(f"{source}: cabecera o final inesperados")

    records = []
    for ln in lines[1:-1]:
        parts = ln.rstrip(";").split(";")
        if len(parts) != 6:
            raise OmieFormatError(f"{source}: línea con {len(parts)} campos: {ln!r}")
        y, m, d, period = (int(x) for x in parts[:4])
        if date(y, m, d) != day:
            raise OmieFormatError(f"{source}: fecha {y}-{m}-{d} distinta de {day}")
        records.append((period, float(parts[4]), float(parts[5])))

    periods = [r[0] for r in records]
    n = len(periods)
    if periods != list(range(1, n + 1)):
        raise OmieFormatError(f"{source}: periodos no consecutivos desde 1")

    hours = day_length_hours(day)
    if n == hours:
        resolution_min = 60
    elif n == hours * 4:
        resolution_min = 15
    else:
        raise OmieFormatError(
            f"{source}: {n} periodos no encaja con un día de {hours} h (ni horario ni 15 min)"
        )

    start_utc = pd.Timestamp(day).tz_localize(TZ_MARKET).tz_convert("UTC")
    ts = start_utc + pd.to_timedelta([(p - 1) * resolution_min for p in periods], unit="min")

    frames = []
    for market, pos in MARKETS.items():
        frames.append(pd.DataFrame({
            "ts_utc": ts,
            "market": market,
            "resolution_min": resolution_min,
            "price_eur_mwh": [r[pos] for r in records],
            "source": source,
        }))
    return pd.concat(frames, ignore_index=True)


def fetch_day(day: date, raw_dir: Path | None = None,
              session: requests.Session | None = None,
              pause_s: float = 0.3) -> str | None:
    """
    Devuelve el texto del fichero del día, o None si OMIE aún no lo ha publicado.
    Si `raw_dir` está definido, guarda el fichero original y lo reutiliza después
    (así repetir un backfill no vuelve a descargar nada).
    """
    name = file_name(day)
    cached = raw_dir / name if raw_dir else None
    if cached and cached.exists():
        return cached.read_text(encoding="latin-1")

    http = session or requests.Session()
    resp = http.get(URL_TEMPLATE.format(yyyymmdd=f"{day:%Y%m%d}"),
                    headers={"User-Agent": USER_AGENT}, timeout=30)
    time.sleep(pause_s)                        # cortesía con el servidor de OMIE
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    text = resp.content.decode("latin-1")
    if not text.startswith("MARGINALPDBC"):
        raise OmieFormatError(f"{name}: la respuesta no es un fichero marginalpdbc")

    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(text, encoding="latin-1")
    return text


def load_day(day: date, raw_dir: Path | None = None,
             session: requests.Session | None = None) -> pd.DataFrame | None:
    """Descarga (o lee de caché) y normaliza un día. None si no está publicado."""
    text = fetch_day(day, raw_dir=raw_dir, session=session)
    if text is None:
        return None
    return parse_marginalpdbc(text, day, source=f"{SOURCE_PREFIX} {file_name(day)}")
