from datetime import date

import pandas as pd

from src.analytics.bess_daily import compute_bess_daily, compute_for_battery
from src.bess_arbitrage import BatteryParams
from src.ingest.omie import parse_marginalpdbc
from tests.conftest import FIXTURES


def fixture_prices(*days: str) -> pd.DataFrame:
    frames = []
    for d in days:
        text = (FIXTURES / f"marginalpdbc_{d}.1").read_text(encoding="latin-1")
        df = parse_marginalpdbc(text, date(int(d[:4]), int(d[4:6]), int(d[6:])), "test")
        frames.append(df[df["market"] == "ES"])
    return pd.concat(frames, ignore_index=True)


def test_dias_de_cambio_de_hora_en_su_fecha_local():
    prices = fixture_prices("20250330", "20241027", "20260329", "20251026")
    out = compute_bess_daily(prices)
    n = out[(out.method == "optimal") & (out.duration_h == 2)].set_index("date")["n_periods"]
    assert n.to_dict() == {"2024-10-27": 25, "2025-03-30": 23, "2025-10-26": 100, "2026-03-29": 92}


def test_filas_por_duracion_y_metodo():
    out = compute_bess_daily(fixture_prices("20250301", "20251001"))
    assert len(out) == 2 * 3 * 2                  # días × duraciones × métodos
    assert set(out["duration_h"]) == {1, 2, 4}
    assert (out["rte"] == 0.88).all()
    assert (out["max_cycles_per_day"] == 1.0).all()


def test_optimo_menor_o_igual_que_simple_por_dia():
    out = compute_bess_daily(fixture_prices("20251001", "20260925", "20260928"))
    piv = out.pivot_table(index=["date", "duration_h"], columns="method",
                          values="revenue_eur_per_mw")
    assert (piv["optimal"] <= piv["simple"] + 0.011).all()


def test_calculadora_coincide_con_bess_daily():
    prices = fixture_prices("20250301", "20251001", "20251026")
    tabla = compute_bess_daily(prices)
    tabla = tabla[(tabla.method == "optimal") & (tabla.duration_h == 2)].set_index("date")
    calc = compute_for_battery(prices, BatteryParams(1, 2, 0.88)).set_index("date")
    assert (calc["revenue_eur_per_mw"] == tabla["revenue_eur_per_mw"]).all()


def test_calculadora_filtra_periodo_y_escala_con_la_potencia():
    prices = fixture_prices("20250301", "20251001", "20251026")
    calc = compute_for_battery(prices, BatteryParams(10, 20, 0.88),
                               start=date(2025, 10, 1), end=date(2025, 10, 26))
    assert list(calc["date"]) == ["2025-10-01", "2025-10-26"]
    # 10 MW / 20 MWh gana 10 veces lo que 1 MW / 2 MWh
    base = compute_for_battery(prices, BatteryParams(1, 2, 0.88),
                               start=date(2025, 10, 1)).set_index("date")
    assert (calc.set_index("date")["revenue_eur"] - 10 * base["revenue_eur"]).abs().max() < 0.2


def test_calculadora_periodo_sin_datos():
    prices = fixture_prices("20250301")
    assert compute_for_battery(prices, BatteryParams(), start=date(2026, 1, 1)).empty


def test_dia_incompleto_se_descarta():
    prices = fixture_prices("20251001", "20250301")   # 96 cuartos + 24 horas
    incompleto = prices.iloc[:60]                     # 60 de los 96 cuartos del 1-oct-2025
    out = compute_bess_daily(pd.concat([incompleto, prices.iloc[96:]]))
    assert set(out["date"]) == {"2025-03-01"}
