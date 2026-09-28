import pytest

from src.analytics.finance import InvestmentParams, evaluate


def test_retorno_simple_a_mano():
    # 1.000.000 € de inversión, 300.000 € de ingreso y 50.000 € de O&M → 250.000 €/año
    r = evaluate(InvestmentParams(capex_eur=1_000_000, annual_revenue_eur=300_000,
                                  om_eur_per_year=50_000, lifetime_years=10))
    assert r.payback_years == pytest.approx(4.0)
    assert r.npv_eur == pytest.approx(10 * 250_000 - 1_000_000)   # tasa 0 → suma simple


def test_retorno_con_decimales():
    # 100 de inversión, 40 al año → 2,5 años
    r = evaluate(InvestmentParams(capex_eur=100, annual_revenue_eur=40, lifetime_years=5))
    assert r.payback_years == pytest.approx(2.5)


def test_degradacion_reduce_ingresos():
    r = evaluate(InvestmentParams(capex_eur=100, annual_revenue_eur=100, degradation=0.1,
                                  lifetime_years=3))
    assert r.cashflows["revenue_eur"].tolist() == pytest.approx([0, 100, 90, 81])


def test_descontado_tarda_mas_y_van_coherente():
    p = InvestmentParams(capex_eur=1000, annual_revenue_eur=200, discount_rate=0.08,
                         lifetime_years=15)
    r = evaluate(p)
    assert r.discounted_payback_years > r.payback_years
    # VAN de una renta constante: C · (1 − (1+r)^−n) / r − inversión
    annuity = 200 * (1 - 1.08 ** -15) / 0.08
    assert r.npv_eur == pytest.approx(annuity - 1000)


def test_tir_hace_cero_el_van():
    r = evaluate(InvestmentParams(capex_eur=1000, annual_revenue_eur=200, lifetime_years=10))
    assert r.irr == pytest.approx(0.1510, abs=1e-4)     # TIR conocida de esta renta
    r2 = evaluate(InvestmentParams(capex_eur=1000, annual_revenue_eur=200,
                                   discount_rate=r.irr, lifetime_years=10))
    assert r2.npv_eur == pytest.approx(0, abs=1e-6)


def test_no_se_recupera_en_la_vida_util():
    r = evaluate(InvestmentParams(capex_eur=1000, annual_revenue_eur=50, lifetime_years=10))
    assert r.payback_years is None
    assert r.discounted_payback_years is None
    assert r.irr is None
    assert r.npv_eur < 0
