"""Ingresos diarios de arbitraje por duración (lee la tabla bess_daily)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import branding, footer, setup_page, t
from src.analytics.bess_daily import MAX_CYCLES_PER_DAY, RTE
from src.bess_arbitrage import annual_summary
from src.db.connection import get_connection
from src.db.repository import load_bess_daily


@st.cache_data(ttl=3600)
def load_daily() -> pd.DataFrame:
    df = load_bess_daily(get_connection(), method="optimal")
    return df[(df["rte"] == RTE) & (df["max_cycles_per_day"] == MAX_CYCLES_PER_DAY)]


lang = setup_page("page_daily")
st.title(t(lang, "daily_title"))
st.caption(t(lang, "daily_caption", rte=RTE, cycles=MAX_CYCLES_PER_DAY))

daily = load_daily()
if daily.empty:
    st.info(t(lang, "no_data"))
    footer(lang)
    st.stop()

durations = sorted(daily["duration_h"].unique())
st.caption(t(lang, "period", start=daily["date"].min(), end=daily["date"].max(),
             days=daily["date"].nunique()))

# Cifras clave: ingreso anual equivalente por duración
for col, dur in zip(st.columns(len(durations)), durations):
    kpi = annual_summary(daily[daily["duration_h"] == dur])
    col.metric(t(lang, "kpi_year", dur=f"{dur:g}"),
               f"{kpi['revenue_eur_per_mw_year_equiv']:,.0f} €".replace(",", "."))

smooth = st.toggle(t(lang, "smoothing"), value=True)

colors = branding()["colors"]["series"]
fig = go.Figure()
for i, dur in enumerate(durations):
    s = (daily[daily["duration_h"] == dur]
         .set_index(pd.to_datetime(daily.loc[daily["duration_h"] == dur, "date"]))
         ["revenue_eur_per_mw"].sort_index())
    if smooth:
        s = s.rolling(7, min_periods=7).mean()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines", name=f"{dur:g} h",
        line=dict(width=2, color=colors[i % len(colors)]),
        hovertemplate="%{y:,.0f} €/MW",
    ))
fig.update_layout(
    hovermode="x unified",
    yaxis_title=t(lang, "y_axis"),
    legend=dict(title=t(lang, "duration"), orientation="h", y=1.08, x=0),
    margin=dict(l=10, r=10, t=40, b=10),
    height=450,
)
fig.update_yaxes(rangemode="tozero")
st.plotly_chart(fig, width="stretch")

with st.expander(t(lang, "data_table")):
    table = (daily.pivot_table(index="date", columns="duration_h", values="revenue_eur_per_mw")
             .rename(columns=lambda d: f"{d:g} h")
             .sort_index(ascending=False))
    st.dataframe(table, width="stretch")

footer(lang)
