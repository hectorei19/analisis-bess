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
- Versiones: el fichero se llama marginalpdbc_AAAAMMDD.v. OMIE solo conserva la
  última versión; si corrige un día, la .1 desaparece y queda la .2, .3...
  (comprobado, p. ej. 30-10-2025 → .3 y 27-11-2025 → .2).
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

URL_TEMPLATE = (
    "https://www.omie.es/es/file-download"
    "?parents=marginalpdbc&filename={name}"
)
MAX_VERSION = 9
SOURCE_PREFIX = "OMIE marginalpdbc"
TZ_MARKET = "Europe/Madrid"
MARKETS = {"PT": 1, "ES": 2}          # posición en cada registro (periodo, PT, ES)
USER_AGENT = "BESS-analytics/0.1 (analisis de mercado)"


class OmieFormatError(ValueError):
    """El fichero no tiene el formato esperado: mejor parar que guardar datos dudosos."""


def file_name(day: date, version: int = 1) -> str:
    return f"marginalpdbc_{day:%Y%m%d}.{version}"


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


def _cached_files(raw_dir: Path, day: date) -> list[Path]:
    """Ficheros del día ya guardados, de menor a mayor versión."""
    files = raw_dir.glob(f"marginalpdbc_{day:%Y%m%d}.*")
    return sorted(files, key=lambda f: int(f.suffix[1:]))


def fetch_day(day: date, raw_dir: Path | None = None,
              session: requests.Session | None = None,
              refresh: bool = False,
              pause_s: float = 0.3) -> tuple[str, str] | None:
    """
    Devuelve (nombre_fichero, texto) de la versión vigente del día, o None si
    OMIE aún no lo ha publicado.

    Si `raw_dir` está definido, guarda el fichero original y lo reutiliza después
    (así repetir un backfill no vuelve a descargar nada). Con `refresh=True` se
    ignora la caché y se vuelve a consultar OMIE (para detectar correcciones).
    """
    if raw_dir and not refresh:
        cached = _cached_files(raw_dir, day)
        if cached:
            return cached[-1].name, cached[-1].read_text(encoding="latin-1")

    http = session or requests.Session()
    for version in range(1, MAX_VERSION + 1):
        name = file_name(day, version)
        resp = http.get(URL_TEMPLATE.format(name=name),
                        headers={"User-Agent": USER_AGENT}, timeout=30)
        time.sleep(pause_s)                    # cortesía con el servidor de OMIE
        if resp.status_code == 404:
            continue                           # esa versión no existe: probar la siguiente
        resp.raise_for_status()
        text = resp.content.decode("latin-1")
        if not text.startswith("MARGINALPDBC"):
            raise OmieFormatError(f"{name}: la respuesta no es un fichero marginalpdbc")
        if raw_dir:
            raw_dir.mkdir(parents=True, exist_ok=True)
            for old in _cached_files(raw_dir, day):   # solo se conserva la vigente
                old.unlink()
            (raw_dir / name).write_text(text, encoding="latin-1")
        return name, text
    return None


def load_day(day: date, raw_dir: Path | None = None,
             session: requests.Session | None = None,
             refresh: bool = False) -> pd.DataFrame | None:
    """Descarga (o lee de caché) y normaliza un día. None si no está publicado."""
    found = fetch_day(day, raw_dir=raw_dir, session=session, refresh=refresh)
    if found is None:
        return None
    name, text = found
    return parse_marginalpdbc(text, day, source=f"{SOURCE_PREFIX} {name}")
