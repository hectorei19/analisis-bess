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

# ─── Parámetros ──────────────────────────────────────────────────────────────
with st.form("params"):
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
    st.form_submit_button(t(lang, "calculate"), type="primary")

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

color = branding()["colors"]["series"][0]
revenue = daily.set_index(pd.to_datetime(daily["date"]))["revenue_eur"].sort_index()

col_daily, col_month = st.columns(2)
with col_daily:
    st.subheader(t(lang, "daily_chart"))
    smooth = st.toggle(t(lang, "smoothing"), value=len(revenue) > 60)
    y = revenue.rolling(7, min_periods=7).mean() if smooth else revenue
    fig = go.Figure(go.Scatter(x=y.index, y=y.values, mode="lines",
                               line=dict(width=2, color=color),
                               hovertemplate="%{x|%d/%m/%Y}: %{y:,.0f} €<extra></extra>"))
    fig.update_layout(yaxis_title=t(lang, "y_day"), height=380,
                      margin=dict(l=10, r=10, t=10, b=10), hovermode="x")
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, width="stretch")

with col_month:
    st.subheader(t(lang, "monthly_chart"))
    by_month = revenue.groupby(revenue.index.to_period("M"))
    monthly = by_month.sum()
    complete = by_month.size() == monthly.index.days_in_month
    fig = go.Figure(go.Bar(x=monthly.index.to_timestamp(), y=monthly.values,
                           marker=dict(color=color, cornerradius=4,
                                       opacity=[1.0 if c else 0.35 for c in complete]),
                           customdata=by_month.size().values,
                           hovertemplate="%{x|%m/%Y}: %{y:,.0f} € (%{customdata} d)<extra></extra>"))
    fig.update_layout(yaxis_title=t(lang, "y_month"), height=380, bargap=0.25,
                      margin=dict(l=10, r=10, t=48, b=10))
    fig.update_xaxes(dtick="M1", tickformat="%m/%y")
    st.plotly_chart(fig, width="stretch")
    if not complete.all():
        st.caption(t(lang, "partial_months"))

with st.expander(t(lang, "data_table")):
    table = daily[["date", "revenue_eur", "cycles", "avg_charge_price",
                   "avg_discharge_price", "spread_max_min"]].sort_values("date", ascending=False)
    table.columns = [t(lang, k) for k in ("col_date", "col_revenue", "col_cycles",
                                          "col_buy", "col_sell", "col_spread")]
    st.dataframe(table, width="stretch", hide_index=True)

footer(lang)
