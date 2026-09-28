"""
Esquema de la base de datos.

Convenciones:
- ts_utc: instante de INICIO del periodo, en UTC, como texto ISO
  'YYYY-MM-DDTHH:MM:SSZ' (ordenable alfabéticamente y legible).
- date (bess_daily): día natural en hora de Madrid, 'YYYY-MM-DD'.
"""

TABLES = [
    """
    CREATE TABLE IF NOT EXISTS prices (
        ts_utc          TEXT    NOT NULL,
        market          TEXT    NOT NULL,   -- 'ES' o 'PT'
        resolution_min  INTEGER NOT NULL,   -- 60 o 15
        price_eur_mwh   REAL    NOT NULL,
        source          TEXT    NOT NULL,   -- p. ej. 'OMIE marginalpdbc_20251001.1'
        PRIMARY KEY (ts_utc, market)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bess_daily (
        date                 TEXT    NOT NULL,
        duration_h           REAL    NOT NULL,
        rte                  REAL    NOT NULL,
        method               TEXT    NOT NULL,   -- 'optimal' o 'simple'
        max_cycles_per_day   REAL    NOT NULL,
        revenue_eur_per_mw   REAL    NOT NULL,
        cycles               REAL,
        avg_charge_price     REAL,               -- NULL si no opera ese día
        avg_discharge_price  REAL,
        spread_max_min       REAL,
        n_periods            INTEGER NOT NULL,
        PRIMARY KEY (date, duration_h, rte, method, max_cycles_per_day)
    )
    """,
]


def create_tables(conn) -> None:
    for ddl in TABLES:
        conn.execute(ddl)
    conn.commit()
