import math

import pandas as pd

from src.db.connection import get_connection
from src.db.repository import load_bess_daily, load_prices, save_bess_daily, save_prices


def _prices(values, source="test"):
    ts = pd.date_range("2025-10-26 00:00", periods=len(values), freq="15min", tz="UTC")
    return pd.DataFrame({"ts_utc": ts, "market": "ES", "resolution_min": 15,
                         "price_eur_mwh": values, "source": source})


def test_prices_upsert_no_duplica(tmp_path):
    conn = get_connection(tmp_path / "t.db")
    save_prices(conn, _prices([1.0, 2.0, 3.0]))
    save_prices(conn, _prices([10.0, 20.0, 30.0], source="v2"))   # mismas claves
    df = load_prices(conn, "ES")
    assert len(df) == 3
    assert df["price_eur_mwh"].tolist() == [10.0, 20.0, 30.0]
    assert (df["source"] == "v2").all()
    assert str(df["ts_utc"].dt.tz) == "UTC"


def test_prices_filtro_por_fechas(tmp_path):
    conn = get_connection(tmp_path / "t.db")
    save_prices(conn, _prices([1.0, 2.0, 3.0, 4.0]))
    df = load_prices(conn, "ES",
                     start_utc=pd.Timestamp("2025-10-26 00:15", tz="UTC"),
                     end_utc=pd.Timestamp("2025-10-26 00:45", tz="UTC"))
    assert df["price_eur_mwh"].tolist() == [2.0, 3.0]


def test_bess_daily_upsert_y_nulos(tmp_path):
    conn = get_connection(tmp_path / "t.db")
    row = dict(date="2026-04-15", duration_h=2.0, rte=0.88, method="optimal",
               max_cycles_per_day=1.0, revenue_eur_per_mw=0.0, cycles=0.0,
               avg_charge_price=float("nan"), avg_discharge_price=float("nan"),
               spread_max_min=0.0, n_periods=96)
    save_bess_daily(conn, pd.DataFrame([row]))
    save_bess_daily(conn, pd.DataFrame([row | {"revenue_eur_per_mw": 5.0}]))
    df = load_bess_daily(conn)
    assert len(df) == 1
    assert df.loc[0, "revenue_eur_per_mw"] == 5.0
    assert math.isnan(df.loc[0, "avg_charge_price"])
