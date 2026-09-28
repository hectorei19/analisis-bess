"""
Calculadora de arbitraje: el usuario elige periodo y características de la
batería, y se calcula al momento con los precios guardados (método óptimo).
"""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import branding, footer, setup_page, t
from src.analytics.bess_daily import compute_for_battery
from src.analytics.finance import InvestmentParams, evaluate
from src.bess_arbitrage import BatteryParams, annual_summary
from src.db.connection import get_connection
from src.db.repository import load_prices
from src.db.snapshot import seed_if_empty
from src.ingest.omie import TZ_MARKET


@st.cache_data(ttl=3600)
def load_es_prices() -> pd.DataFrame:
    conn = get_connection()
    seed_if_empty(conn)            # en la web publicada, la base arranca vacía
    return load_prices(conn, "ES")[["ts_utc", "price_eur_mwh"]]


@st.cache_data(max_entries=50)
def compute(start: date, end: date, power: float, energy: float, rte: float,
            cycles: float, soc_min: float, soc_max: float, degradation: float) -> pd.DataFrame:
    bp = BatteryParams(power_mw=power, energy_mwh=energy, rte=rte, soc_min=soc_min,
                       soc_max=soc_max, soc_initial=soc_min,
                       max_cycles_per_day=cycles, degradation_eur_mwh=degradation)
    return compute_for_battery(load_es_prices(), bp, start=start, end=end)


def fmt_eur(x: float, lang: str) -> str:
    s = f"{x:,.0f}"
    return (s.replace(",", ".") + " €") if lang == "es" else ("€" + s)


def fmt_num(x: float, lang: str, decimals: int = 2) -> str:
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") if lang == "es" else s


lang = setup_page("page_calc")
st.title(t(lang, "calc_title"))
st.write(t(lang, "calc_intro"))

prices = load_es_prices()
if prices.empty:
    st.info(t(lang, "no_data"))
    footer(lang)
    st.stop()

local_days = prices["ts_utc"].dt.tz_convert(TZ_MARKET).dt.date
first_day, last_day = local_days.min(), local_days.max()

# ─── Parámetros (cualquier cambio recalcula al momento) ─────────────────────
with st.container(border=True):
    c1, c2, c3 = st.columns([2, 1, 1])
    period = c1.date_input(t(lang, "period_input"),
                           value=(max(first_day, last_day - timedelta(days=364)), last_day),
                           min_value=first_day, max_value=last_day, format="DD/MM/YYYY")
    power = c2.number_input(t(lang, "power"), min_value=0.1, max_value=1000.0,
                            value=1.0, step=0.5)
    energy = c3.number_input(t(lang, "energy"), min_value=0.1, max_value=8000.0,
                             value=2.0, step=0.5)
    c4, c5, c6, c7 = st.columns(4)
    rte_pct = c4.slider(t(lang, "rte"), min_value=60, max_value=98, value=88)
    cycles = c5.number_input(t(lang, "cycles"), min_value=0.25, max_value=4.0,
                             value=1.0, step=0.25)
    soc_min, soc_max = c6.slider(t(lang, "soc"), min_value=0, max_value=100, value=(5, 95))
    degradation = c7.number_input(t(lang, "degradation"), min_value=0.0, max_value=200.0,
                                  value=0.0, step=1.0)

st.caption(t(lang, "duration_info", dur=energy / power))

if not isinstance(period, tuple) or len(period) != 2:
    st.warning(t(lang, "period_incomplete"))
    footer(lang)
    st.stop()
if soc_min >= soc_max:
    st.warning(t(lang, "soc_invalid"))
    footer(lang)
    st.stop()

start, end = period
with st.spinner(t(lang, "computing", days=(end - start).days + 1)):
    daily = compute(start, end, power, energy, rte_pct / 100, cycles,
                    soc_min / 100, soc_max / 100, degradation)

if daily.empty:
    st.warning(t(lang, "no_days"))
    footer(lang)
    st.stop()

# ─── Resultados ──────────────────────────────────────────────────────────────
kpi = annual_summary(daily)
total = daily["revenue_eur"].sum()
k1, k2, k3, k4 = st.columns(4)
k1.metric(t(lang, "kpi_total"), fmt_eur(total, lang))
k2.metric(t(lang, "kpi_year"), fmt_eur(total * 365 / kpi["days"], lang),
          help=t(lang, "kpi_year_mw",
                 value=fmt_num(kpi["revenue_eur_per_mw_year_equiv"], lang, 0)))
k3.metric(t(lang, "kpi_cycles"), fmt_num(kpi["avg_cycles_per_day"], lang))
k4.metric(t(lang, "kpi_days"), f"{kpi['days']}")
st.caption(t(lang, "kpi_year_mw", value=fmt_num(kpi["revenue_eur_per_mw_year_equiv"], lang, 0)))

colors = branding()["colors"]["series"]
d = daily.set_index(pd.to_datetime(daily["date"])).sort_index()
# Importes de compra y venta por día (para medias ponderadas por energía)
d["buy_eur"] = (d["avg_charge_price"] * d["energy_charged_mwh"]).fillna(0.0)
d["sell_eur"] = (d["avg_discharge_price"] * d["energy_discharged_mwh"]).fillna(0.0)

months = d.index.to_period("M")
by_month = d.groupby(months)
n_days = by_month.size()
complete = n_days == n_days.index.days_in_month
month_x = n_days.index.to_timestamp()
opacity = [1.0 if c else 0.35 for c in complete]

smooth = st.toggle(t(lang, "smoothing"), value=len(d) > 60)


def rolling_sum(s: pd.Series) -> pd.Series:
    return s.rolling(7, min_periods=7).sum() if smooth else s


def layout(fig, y_title, top=10):
    fig.update_layout(yaxis_title=y_title, height=360, hovermode="x unified",
                      margin=dict(l=10, r=10, t=top, b=10),
                      legend=dict(orientation="h", y=1.12, x=0))
    return fig


# ─── Ingresos ────────────────────────────────────────────────────────────────
st.subheader(t(lang, "revenue_section"))
col_daily, col_month = st.columns(2)
with col_daily:
    st.caption(t(lang, "daily_chart"))
    y = rolling_sum(d["revenue_eur"]) / (7 if smooth else 1)
    fig = go.Figure(go.Scatter(x=y.index, y=y.values, mode="lines",
                               line=dict(width=2, color=colors[0]),
                               hovertemplate="%{y:,.0f} €<extra></extra>"))
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(layout(fig, t(lang, "y_day")), width="stretch")

with col_month:
    st.caption(t(lang, "monthly_chart"))
    fig = go.Figure(go.Bar(x=month_x, y=by_month["revenue_eur"].sum().values,
                           marker=dict(color=colors[0], cornerradius=4, opacity=opacity),
                           customdata=n_days.values,
                           hovertemplate="%{y:,.0f} € (%{customdata} d)<extra></extra>"))
    fig.update_layout(bargap=0.25)
    fig.update_xaxes(tickformat="%m/%y")
    st.plotly_chart(layout(fig, t(lang, "y_month")), width="stretch")

# ─── Precios medios de compra y venta ────────────────────────────────────────
st.subheader(t(lang, "prices_section"))
st.caption(t(lang, "prices_caption"))
col_daily, col_month = st.columns(2)
with col_daily:
    st.caption(t(lang, "daily_prices_chart"))
    fig = go.Figure()
    for key, eur, mwh, color in (("buy", "buy_eur", "energy_charged_mwh", colors[0]),
                                 ("sell", "sell_eur", "energy_discharged_mwh", colors[1])):
        y = rolling_sum(d[eur]) / rolling_sum(d[mwh]).replace(0, float("nan"))
        fig.add_trace(go.Scatter(x=y.index, y=y.values, mode="lines", name=t(lang, key),
                                 line=dict(width=2, color=color),
                                 hovertemplate="%{y:,.1f} €/MWh"))
    st.plotly_chart(layout(fig, "€/MWh", top=30), width="stretch")

with col_month:
    st.caption(t(lang, "monthly_prices_chart"))
    fig = go.Figure()
    for key, eur, mwh, color in (("buy", "buy_eur", "energy_charged_mwh", colors[0]),
                                 ("sell", "sell_eur", "energy_discharged_mwh", colors[1])):
        y = by_month[eur].sum() / by_month[mwh].sum().replace(0, float("nan"))
        fig.add_trace(go.Bar(x=month_x, y=y.values, name=t(lang, key),
                             marker=dict(color=color, cornerradius=4, opacity=opacity),
                             hovertemplate="%{y:,.1f} €/MWh"))
    fig.update_layout(bargap=0.25, bargroupgap=0.08)
    fig.update_xaxes(tickformat="%m/%y")
    st.plotly_chart(layout(fig, "€/MWh", top=30), width="stretch")

if not complete.all():
    st.caption(t(lang, "partial_months"))

with st.expander(t(lang, "data_table")):
    table = daily[["date", "revenue_eur", "cycles", "avg_charge_price",
                   "avg_discharge_price", "spread_max_min"]].sort_values("date", ascending=False)
    table.columns = [t(lang, k) for k in ("col_date", "col_revenue", "col_cycles",
                                          "col_buy", "col_sell", "col_spread")]
    st.dataframe(table, width="stretch", hide_index=True)

# ─── Inversión y retorno ─────────────────────────────────────────────────────
st.divider()
st.subheader(t(lang, "invest_section"))
annual_revenue = total * 365 / kpi["days"]

with st.container(border=True):
    i1, i2, i3 = st.columns([1.2, 1, 1])
    capex_mode = i1.radio(t(lang, "capex_mode"), ["kwh", "total"], horizontal=True,
                          format_func=lambda m: t(lang, f"capex_mode_{m}"))
    if capex_mode == "kwh":
        capex_kwh = i2.number_input(t(lang, "capex_kwh"), min_value=0.0, max_value=5000.0,
                                    value=200.0, step=10.0)
        capex = capex_kwh * energy * 1000
    else:
        capex = i2.number_input(t(lang, "capex_total"), min_value=0.0, max_value=5e9,
                                value=float(round(200 * energy * 1000)), step=10_000.0)
    om_mw = i3.number_input(t(lang, "om"), min_value=0.0, max_value=1e6,
                            value=10_000.0, step=1_000.0)
    i4, i5, i6 = st.columns(3)
    degr = i4.number_input(t(lang, "degr"), min_value=0.0, max_value=20.0,
                           value=2.0, step=0.5)
    disc = i5.number_input(t(lang, "disc"), min_value=0.0, max_value=30.0,
                           value=7.0, step=0.5)
    life = i6.number_input(t(lang, "life"), min_value=1, max_value=40, value=15, step=1)
    st.caption(t(lang, "invest_defaults"))

res = evaluate(InvestmentParams(capex_eur=capex, annual_revenue_eur=annual_revenue,
                                om_eur_per_year=om_mw * power, degradation=degr / 100,
                                discount_rate=disc / 100, lifetime_years=int(life)))


def fmt_years(y):
    return (t(lang, "years", n=fmt_num(y, lang, 1)) if y is not None
            else t(lang, "not_recovered", n=int(life)))


r1, r2, r3, r4, r5 = st.columns(5)
r1.metric(t(lang, "capex_total_kpi"), fmt_eur(capex, lang))
r2.metric(t(lang, "payback"), fmt_years(res.payback_years))
r3.metric(t(lang, "payback_disc"), fmt_years(res.discounted_payback_years))
r4.metric(t(lang, "npv"), fmt_eur(res.npv_eur, lang))
r5.metric(t(lang, "irr"), f"{fmt_num(res.irr * 100, lang, 1)} %" if res.irr is not None else "—")
st.caption(t(lang, "year1", rev=fmt_eur(annual_revenue, lang),
             om=fmt_eur(om_mw * power, lang)))

cf = res.cashflows
fig = go.Figure()
fig.add_trace(go.Scatter(x=cf["year"], y=cf["cumulative_eur"], mode="lines+markers",
                         name=t(lang, "cum_simple"), line=dict(width=2, color=colors[0]),
                         marker=dict(size=8), hovertemplate="%{y:,.0f} €"))
fig.add_trace(go.Scatter(x=cf["year"], y=cf["discounted_cumulative_eur"], mode="lines+markers",
                         name=t(lang, "cum_disc"), line=dict(width=2, color=colors[1], dash="dash"),
                         marker=dict(size=8), hovertemplate="%{y:,.0f} €"))
fig.add_hline(y=0, line=dict(width=1, color="#898781"))
fig.update_xaxes(title=t(lang, "year_axis"), dtick=1)
st.plotly_chart(layout(fig, t(lang, "cum_axis"), top=30), width="stretch")

with st.expander(t(lang, "cashflow_table")):
    ct = cf.copy()
    ct.columns = [t(lang, k) for k in ("cf_year", "cf_revenue", "cf_om", "cf_capex",
                                       "cf_flow", "cf_cum", "cf_disc_cum")]
    st.dataframe(ct.round(0), width="stretch", hide_index=True)

st.caption(t(lang, "invest_assumptions"))

footer(lang)
