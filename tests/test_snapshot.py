import pandas as pd

from src.db.connection import get_connection
from src.db.repository import load_prices, save_prices
from src.db.snapshot import export_snapshot, seed_if_empty


def _prices():
    ts = pd.date_range("2025-10-26 00:00", periods=4, freq="15min", tz="UTC")
    return pd.concat([
        pd.DataFrame({"ts_utc": ts, "market": m, "resolution_min": 15,
                      "price_eur_mwh": [1.5, -2.0, 3.25, 4.0], "source": "OMIE x.1"})
        for m in ("ES", "PT")
    ], ignore_index=True)


def test_ida_y_vuelta_sin_perdidas(tmp_path):
    origen = get_connection(tmp_path / "a.db")
    save_prices(origen, _prices())
    snap = tmp_path / "prices.csv.gz"
    assert export_snapshot(origen, snap) == 8

    destino = get_connection(tmp_path / "b.db")
    assert seed_if_empty(destino, snap) == 8
    for m in ("ES", "PT"):
        pd.testing.assert_frame_equal(load_prices(destino, m), load_prices(origen, m))


def test_no_toca_una_base_con_datos(tmp_path):
    conn = get_connection(tmp_path / "a.db")
    save_prices(conn, _prices())
    snap = tmp_path / "prices.csv.gz"
    export_snapshot(conn, snap)
    assert seed_if_empty(conn, snap) == 0


def test_sin_archivo_no_hace_nada(tmp_path):
    conn = get_connection(tmp_path / "a.db")
    assert seed_if_empty(conn, tmp_path / "no_existe.csv.gz") == 0
