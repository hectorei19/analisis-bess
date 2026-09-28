"""
Tests del módulo de arbitraje. El principal: el método simple es una cota
superior del óptimo (ingreso óptimo ≤ ingreso simple) en cualquier día.
"""

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import linprog

from src.bess_arbitrage import BatteryParams, arbitrage_optimal, arbitrage_simple
from tests.conftest import omie_fixture_days

TOL = 0.011  # los ingresos se redondean a 2 decimales


def random_days(n, seed=0):
    """Días sintéticos horarios y cuartohorarios, con precios negativos a menudo."""
    rng = np.random.default_rng(seed)
    for i in range(n):
        T = [24, 96][i % 2]
        freq = "h" if T == 24 else "15min"
        p = rng.normal(rng.uniform(-20, 120), rng.uniform(5, 80), T)
        yield pd.Series(p, index=pd.date_range("2026-01-01", periods=T, freq=freq))


PARAMS = [
    BatteryParams(1, dur, rte, max_cycles_per_day=cyc, degradation_eur_mwh=deg)
    for dur in (1, 2, 4)
    for rte in (0.88, 0.8)
    for cyc in (0.5, 1.0, 1.5, 2.0)
    for deg in (0.0, 5.0)
]


def _id(b):
    return f"{b.energy_mwh:g}h-rte{b.rte}-cyc{b.max_cycles_per_day}-deg{b.degradation_eur_mwh:g}"


def relaxed_lp(prices, bp):
    """El problema que resuelve arbitrage_simple, resuelto con linprog (referencia)."""
    p = prices.to_numpy()
    dt = 1.0 if len(p) <= 25 else 0.25
    T = len(p)
    c = np.concatenate([p * dt, -(p - bp.degradation_eur_mwh) * dt])
    A = np.zeros((2, 2 * T))
    A[0, :T] = -bp.rte * dt          # Σd·dt − rte·Σc·dt ≤ 0
    A[0, T:] = dt
    A[1, T:] = dt                    # Σd·dt ≤ ciclos · E_útil
    b = [0.0, bp.max_cycles_per_day * bp.usable_mwh]
    sol = linprog(c, A_ub=A, b_ub=b, bounds=[(0, bp.power_mw)] * 2 * T, method="highs")
    assert sol.success
    return -sol.fun / bp.power_mw


@pytest.mark.parametrize("bp", PARAMS, ids=_id)
def test_optimo_menor_o_igual_que_simple(bp):
    days = list(omie_fixture_days().values()) + list(random_days(60))
    for s in days:
        rs, _ = arbitrage_simple(s, bp)
        ro, _ = arbitrage_optimal(s, bp)
        assert ro.revenue_eur_per_mw <= rs.revenue_eur_per_mw + TOL, (s.index[0], rs, ro)


@pytest.mark.parametrize("bp", PARAMS[::3], ids=_id)
def test_simple_es_exacto_para_la_relajacion(bp):
    for s in list(random_days(60, seed=1)) + list(omie_fixture_days().values()):
        rs, _ = arbitrage_simple(s, bp)
        assert rs.revenue_eur_per_mw == pytest.approx(relaxed_lp(s, bp), abs=TOL)


def test_simple_respeta_potencia_perdidas_y_ciclos():
    bp = BatteryParams(2, 4, 0.88, max_cycles_per_day=1.5)
    for s in random_days(50, seed=2):
        _, sch = arbitrage_simple(s, bp)
        dt = 1.0 if len(s) == 24 else 0.25
        assert sch["charge_mw"].between(0, bp.power_mw + 1e-9).all()
        assert sch["discharge_mw"].between(0, bp.power_mw + 1e-9).all()
        e_dis = sch["discharge_mw"].sum() * dt
        assert e_dis <= bp.rte * sch["charge_mw"].sum() * dt + 1e-9
        assert e_dis <= bp.max_cycles_per_day * bp.usable_mwh + 1e-9


def test_simple_ejemplo_a_mano():
    # 1 MW / 1 MWh, rte 0,8, 1 ciclo → E_útil 0,9 MWh.
    # Compra 0,9/0,8 = 1,125 MWh: 1 MWh a 10 €/MWh + 0,125 MWh a 20 €/MWh = 12,5 €
    # Vende 0,9 MWh a 100 €/MWh = 90 €  → ingreso 77,5 €
    p = [10, 20, 50, 50, 50, 100] + [50] * 18
    s = pd.Series(p, index=pd.date_range("2026-01-01", periods=24, freq="h"), dtype=float)
    r, _ = arbitrage_simple(s, BatteryParams(1, 1, 0.8, max_cycles_per_day=1.0))
    assert r.revenue_eur_per_mw == pytest.approx(77.5)
    assert r.cycles == pytest.approx(1.0)


def test_simple_con_precios_negativos():
    # Mediodía solar a −5 €/MWh, resto a 80: nunca vende a precio negativo
    p = [80] * 8 + [-5] * 8 + [80] * 8
    s = pd.Series(p, index=pd.date_range("2026-04-15", periods=24, freq="h"), dtype=float)
    bp = BatteryParams(1, 2, 0.88, max_cycles_per_day=1.0)
    rs, sch = arbitrage_simple(s, bp)
    ro, _ = arbitrage_optimal(s, bp)
    assert (sch.loc[sch["price"] < 0, "discharge_mw"] == 0).all()
    assert ro.revenue_eur_per_mw <= rs.revenue_eur_per_mw + TOL
    assert rs.revenue_eur_per_mw == pytest.approx(relaxed_lp(s, bp), abs=TOL)


def test_precios_planos_no_opera():
    s = pd.Series(50.0, index=pd.date_range("2026-01-01", periods=24, freq="h"))
    rs, _ = arbitrage_simple(s, BatteryParams(1, 2, 0.88))
    ro, _ = arbitrage_optimal(s, BatteryParams(1, 2, 0.88))
    assert rs.revenue_eur_per_mw == 0
    assert ro.revenue_eur_per_mw == 0


def test_regresion_28sep2026():
    # Día real en el que la versión anterior del método simple quedaba por debajo del óptimo
    s = omie_fixture_days()["20260928"]
    bp = BatteryParams(1, 4, 0.88, max_cycles_per_day=1.0)
    rs, _ = arbitrage_simple(s, bp)
    ro, _ = arbitrage_optimal(s, bp)
    assert ro.revenue_eur_per_mw == pytest.approx(298.35, abs=0.02)
    assert rs.revenue_eur_per_mw >= ro.revenue_eur_per_mw


def test_horario_y_cuartohorario_equivalentes():
    # Los mismos precios en 24 horas o repetidos en 96 cuartos dan el mismo ingreso óptimo
    s = omie_fixture_days()["20250301"]
    s15 = pd.Series(np.repeat(s.to_numpy(), 4),
                    index=pd.date_range("2025-03-01", periods=96, freq="15min"))
    bp = BatteryParams(1, 2, 0.88)
    assert arbitrage_optimal(s15, bp)[0].revenue_eur_per_mw == pytest.approx(
        arbitrage_optimal(s, bp)[0].revenue_eur_per_mw, abs=0.05)
