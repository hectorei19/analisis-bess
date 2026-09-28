"""
Funciones de lectura y escritura. Es la única parte del proyecto que escribe SQL.

Todas reciben una conexión de `src.db.connection.get_connection()`. Las
escrituras son "upsert": si la fila ya existe (misma clave) se actualiza en vez
de duplicarse, así que se pueden repetir sin miedo.
"""

from __future__ import annotations

import math

import pandas as pd

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

PRICE_COLUMNS = ["ts_utc", "market", "resolution_min", "price_eur_mwh", "source"]
BESS_DAILY_COLUMNS = [
    "date", "duration_h", "rte", "method", "max_cycles_per_day",
    "revenue_eur_per_mw", "cycles", "avg_charge_price", "avg_discharge_price",
    "spread_max_min", "n_periods",
]
BESS_DAILY_KEY = ["date", "duration_h", "rte", "method", "max_cycles_per_day"]


def _none_if_nan(v):
    return None if isinstance(v, float) and math.isnan(v) else v


def _upsert(conn, table: str, columns: list[str], key: list[str], rows: list[tuple]) -> int:
    cols = ", ".join(columns)
    marks = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{c} = excluded.{c}" for c in columns if c not in key)
    sql = (f"INSERT INTO {table} ({cols}) VALUES ({marks}) "
           f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {updates}")
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def _fetch_df(conn, sql: str, params: tuple = ()) -> pd.DataFrame:
    cur = conn.execute(sql, params)
    columns = [d[0] for d in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=columns)


# ─── prices ──────────────────────────────────────────────────────────────────
def save_prices(conn, df: pd.DataFrame) -> int:
    """Guarda precios. `df.ts_utc` debe tener zona horaria (se convierte a UTC)."""
    if df.empty:
        return 0
    ts = pd.DatetimeIndex(df["ts_utc"])
    if ts.tz is None:
        raise ValueError("ts_utc debe tener zona horaria (tz-aware)")
    ts_txt = ts.tz_convert("UTC").strftime(TS_FORMAT)
    rows = [
        (t, str(m), int(r), float(p), str(s))
        for t, m, r, p, s in zip(ts_txt, df["market"], df["resolution_min"],
                                 df["price_eur_mwh"], df["source"])
    ]
    return _upsert(conn, "prices", PRICE_COLUMNS, ["ts_utc", "market"], rows)


def load_prices(conn, market: str = "ES",
                start_utc: pd.Timestamp | None = None,
                end_utc: pd.Timestamp | None = None) -> pd.DataFrame:
    """
    Precios de un mercado, ordenados, con `ts_utc` como Timestamp UTC.
    `start_utc` incluido, `end_utc` excluido.
    """
    sql = "SELECT * FROM prices WHERE market = ?"
    params: list = [market]
    if start_utc is not None:
        sql += " AND ts_utc >= ?"
        params.append(pd.Timestamp(start_utc).tz_convert("UTC").strftime(TS_FORMAT))
    if end_utc is not None:
        sql += " AND ts_utc < ?"
        params.append(pd.Timestamp(end_utc).tz_convert("UTC").strftime(TS_FORMAT))
    df = _fetch_df(conn, sql + " ORDER BY ts_utc", tuple(params))
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], format=TS_FORMAT, utc=True)
    return df


# ─── bess_daily ──────────────────────────────────────────────────────────────
def save_bess_daily(conn, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    rows = [
        tuple(_none_if_nan(v) for v in rec)
        for rec in df[BESS_DAILY_COLUMNS].astype(object).itertuples(index=False, name=None)
    ]
    return _upsert(conn, "bess_daily", BESS_DAILY_COLUMNS, BESS_DAILY_KEY, rows)


def load_bess_daily(conn, method: str | None = None) -> pd.DataFrame:
    sql = "SELECT * FROM bess_daily"
    params: tuple = ()
    if method is not None:
        sql += " WHERE method = ?"
        params = (method,)
    df = _fetch_df(conn, sql + " ORDER BY date, duration_h", params)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    numeric = [c for c in BESS_DAILY_COLUMNS if c not in ("date", "method")]
    df[numeric] = df[numeric].apply(pd.to_numeric)   # NULL → NaN
    return df
