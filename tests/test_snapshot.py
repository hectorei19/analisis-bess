import pandas as pd

from src.db.connection import get_connection
from src.db.repository import load_prices, save_prices
from src.db.snapshot import export_snapshot, sync_from_snapshot


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
    assert sync_from_snapshot(destino, snap) == 8
    for m in ("ES", "PT"):
        pd.testing.assert_frame_equal(load_prices(destino, m), load_prices(origen, m))


def test_no_toca_una_base_con_datos(tmp_path):
    conn = get_connection(tmp_path / "a.db")
    save_prices(conn, _prices())
    snap = tmp_path / "prices.csv.gz"
    export_snapshot(conn, snap)
    assert sync_from_snapshot(conn, snap) == 0


def test_base_antigua_se_actualiza_con_archivo_nuevo(tmp_path):
    # Como la web publicada: base creada con un archivo viejo y luego llega uno con más días
    completo = get_connection(tmp_path / "completo.db")
    save_prices(completo, _prices())
    snap = tmp_path / "prices.csv.gz"
    export_snapshot(completo, snap)

    nube = get_connection(tmp_path / "nube.db")
    save_prices(nube, _prices().iloc[[0, 4]])          # solo el primer periodo ES y PT
    assert sync_from_snapshot(nube, snap) == 8
    assert len(load_prices(nube, "ES")) == 4


def test_sin_archivo_no_hace_nada(tmp_path):
    conn = get_connection(tmp_path / "a.db")
    assert sync_from_snapshot(conn, tmp_path / "no_existe.csv.gz") == 0
