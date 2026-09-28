from datetime import date

import pandas as pd
import pytest

from src.ingest.omie import OmieFormatError, day_length_hours, load_day, parse_marginalpdbc
from tests.conftest import FIXTURES


def parse_fixture(yyyymmdd: str) -> pd.DataFrame:
    day = date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:]))
    text = (FIXTURES / f"marginalpdbc_{yyyymmdd}.1").read_text(encoding="latin-1")
    return parse_marginalpdbc(text, day, source="test")


def es(df):
    return df[df["market"] == "ES"].reset_index(drop=True)


def utc(s):
    return pd.Timestamp(s, tz="UTC")


def test_dia_horario_normal():
    df = es(parse_fixture("20250301"))
    assert len(df) == 24
    assert (df["resolution_min"] == 60).all()
    assert df["ts_utc"].iloc[0] == utc("2025-02-28 23:00")    # 00:00 en Madrid (UTC+1)
    assert df["price_eur_mwh"].iloc[0] == 105.36
    assert df["price_eur_mwh"].iloc[-1] == 66.28


def test_cuartohorario_normal():
    df = es(parse_fixture("20251001"))
    assert len(df) == 96
    assert (df["resolution_min"] == 15).all()
    assert df["ts_utc"].iloc[0] == utc("2025-09-30 22:00")    # 00:00 en Madrid (UTC+2)
    assert df["ts_utc"].iloc[-1] == utc("2025-10-01 21:45")
    assert (df["ts_utc"].diff().dropna().dt.total_seconds() == 900).all()


@pytest.mark.parametrize("yyyymmdd, n, res, first, last", [
    ("20250330", 23, 60, "2025-03-29 23:00", "2025-03-30 21:00"),   # marzo, horario
    ("20241027", 25, 60, "2024-10-26 22:00", "2024-10-27 22:00"),   # octubre, horario
    ("20260329", 92, 15, "2026-03-28 23:00", "2026-03-29 21:45"),   # marzo, 15 min
    ("20251026", 100, 15, "2025-10-25 22:00", "2025-10-26 22:45"),  # octubre, 15 min
])
def test_dias_de_cambio_de_hora(yyyymmdd, n, res, first, last):
    df = es(parse_fixture(yyyymmdd))
    assert len(df) == n
    assert (df["resolution_min"] == res).all()
    assert df["ts_utc"].iloc[0] == utc(first)
    assert df["ts_utc"].iloc[-1] == utc(last)
    assert df["ts_utc"].is_unique
    assert (df["ts_utc"].diff().dropna().dt.total_seconds() == res * 60).all()
    # En hora de Madrid, todos los periodos caen en el mismo día natural
    local = df["ts_utc"].dt.tz_convert("Europe/Madrid")
    assert local.dt.strftime("%Y%m%d").eq(yyyymmdd).all()


def test_no_confunde_espana_y_portugal():
    # Línea real: 2026;09;25;45;110.03;93.89;  (PT primero, ES después)
    df = parse_fixture("20260925")
    ts = utc("2026-09-25 09:00")          # periodo 45 = 11:00 en Madrid
    row = df[df["ts_utc"] == ts].set_index("market")["price_eur_mwh"]
    assert row["ES"] == 93.89
    assert row["PT"] == 110.03


def test_duracion_de_los_dias():
    assert day_length_hours(date(2026, 3, 29)) == 23
    assert day_length_hours(date(2025, 10, 26)) == 25
    assert day_length_hours(date(2026, 6, 1)) == 24


@pytest.mark.parametrize("texto, motivo", [
    ("<html>error</html>", "cabecera"),
    ("MARGINALPDBC;\n2025;03;01;1;10;10;\n2025;03;01;3;10;10;\n*", "consecutivos"),
    ("MARGINALPDBC;\n2025;03;02;1;10;10;\n*", "distinta"),
    ("MARGINALPDBC;\n" + "".join(f"2025;03;01;{i};10;10;\n" for i in range(1, 24)) + "*",
     "no encaja"),
])
def test_formato_inesperado_se_rechaza(texto, motivo):
    with pytest.raises(OmieFormatError, match=motivo):
        parse_marginalpdbc(texto, date(2025, 3, 1), source="test")


def test_load_day_usa_la_cache_sin_descargar(tmp_path):
    (tmp_path / "marginalpdbc_20250301.1").write_bytes(
        (FIXTURES / "marginalpdbc_20250301.1").read_bytes())

    class SinRed:
        def get(self, *a, **k):
            raise AssertionError("no debería descargar nada")

    df = load_day(date(2025, 3, 1), raw_dir=tmp_path, session=SinRed())
    assert len(df) == 48                   # 24 periodos × 2 mercados
    assert (df["source"] == "OMIE marginalpdbc marginalpdbc_20250301.1").all()
