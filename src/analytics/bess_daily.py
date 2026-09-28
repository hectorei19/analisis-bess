"""
Cálculo de la tabla `bess_daily`: ingreso diario de arbitraje por duración de
batería, a partir de los precios guardados en la tabla `prices`.
"""

from __future__ import annotations

import pandas as pd

from src.bess_arbitrage import BatteryParams, run_period
from src.db.repository import BESS_DAILY_COLUMNS
from src.ingest.omie import TZ_MARKET, day_length_hours

DURATIONS_H = (1, 2, 4)
RTE = 0.88
MAX_CYCLES_PER_DAY = 1.0
METHODS = ("optimal", "simple")


def complete_days_only(prices: pd.Series) -> pd.Series:
    """
    Deja solo los días (hora de Madrid) con todos sus periodos: 23/24/25 si es
    horario o 92/96/100 si es cuartohorario. Evita calcular días a medias.
    """
    local_day = prices.index.tz_convert(TZ_MARKET).date
    counts = pd.Series(local_day).value_counts()
    ok = {d for d, n in counts.items() if n in (day_length_hours(d), 4 * day_length_hours(d))}
    return prices[[d in ok for d in local_day]]


def compute_bess_daily(prices_utc: pd.DataFrame,
                       durations_h=DURATIONS_H, rte: float = RTE,
                       max_cycles_per_day: float = MAX_CYCLES_PER_DAY,
                       methods=METHODS) -> pd.DataFrame:
    """
    `prices_utc`: filas de la tabla `prices` de UN mercado (columnas ts_utc,
    price_eur_mwh). Devuelve filas con las columnas de `bess_daily`.
    """
    if prices_utc.empty:
        return pd.DataFrame(columns=BESS_DAILY_COLUMNS)
    s = pd.Series(prices_utc["price_eur_mwh"].to_numpy(dtype=float),
                  index=pd.DatetimeIndex(prices_utc["ts_utc"]), name="price_eur_mwh")
    s = complete_days_only(s.sort_index())

    frames = []
    for method in methods:
        for dur in durations_h:
            bp = BatteryParams(power_mw=1.0, energy_mwh=float(dur), rte=rte,
                               max_cycles_per_day=max_cycles_per_day)
            daily = run_period(s, bp, method=method, tz=TZ_MARKET)
            daily["max_cycles_per_day"] = max_cycles_per_day
            frames.append(daily)
    out = pd.concat(frames, ignore_index=True)
    return out[BESS_DAILY_COLUMNS]
