"""
bess_arbitrage.py — Cálculo de ingresos de arbitraje de una batería (BESS)
en el mercado diario español (OMIE / e·sios).

Dos métodos:
  - arbitrage_simple():  cálculo rápido sin optimizador que ignora el orden
                         temporal → es una COTA SUPERIOR garantizada del óptimo.
  - arbitrage_optimal(): optimización lineal (scipy / HiGHS) que respeta el
                         estado de carga periodo a periodo. Es la que se debe
                         usar para cifras publicadas o informes.

Funciona con resolución horaria (24 valores, 23/25 en cambio de hora) y
cuartohoraria (96 valores; el mercado diario europeo pasó a MTU de 15 min
en octubre de 2025). El paso temporal se deduce de los timestamps.

Limitaciones conocidas (a comunicar en la web):
  - Solo arbitraje en el mercado diario, con previsión perfecta (precios conocidos).
  - No incluye intradía, servicios de ajuste, peajes, ni coste real de degradación
    (solo un coste opcional €/MWh descargado).
  - Con precios negativos, un LP puede cargar y descargar a la vez para "quemar"
    energía en pérdidas. Se evita con `forbid_simultaneous=True` (penalización leve).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
from scipy.optimize import linprog


# ─────────────────────────────────────────────────────────────────────────────
# Parámetros de la batería
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class BatteryParams:
    power_mw: float = 1.0              # potencia nominal (carga y descarga)
    energy_mwh: float = 2.0            # capacidad nominal → duración = energy/power
    rte: float = 0.88                  # eficiencia de ida y vuelta (round-trip)
    soc_min: float = 0.05              # fracción mínima de SoC
    soc_max: float = 0.95              # fracción máxima de SoC
    soc_initial: float = 0.05          # SoC al inicio del día (y exigido al final)
    max_cycles_per_day: float = 1.0    # ciclos equivalentes de descarga por día
    degradation_eur_mwh: float = 0.0   # coste por MWh descargado (proxy degradación)

    @property
    def duration_h(self) -> float:
        return self.energy_mwh / self.power_mw

    @property
    def usable_mwh(self) -> float:
        return self.energy_mwh * (self.soc_max - self.soc_min)

    def validate(self) -> None:
        assert self.power_mw > 0 and self.energy_mwh > 0
        assert 0 < self.rte <= 1
        assert 0 <= self.soc_min < self.soc_max <= 1
        assert self.soc_min <= self.soc_initial <= self.soc_max
        assert self.max_cycles_per_day > 0


@dataclass
class DailyResult:
    date: str
    method: str
    revenue_eur: float                # ingreso neto del día (descarga − carga − degradación)
    revenue_eur_per_mw: float
    energy_charged_mwh: float
    energy_discharged_mwh: float
    cycles: float                     # MWh descargados / MWh útiles
    avg_charge_price: float           # €/MWh medio de compra
    avg_discharge_price: float        # €/MWh medio de venta
    spread_max_min: float             # precio máx − mín del día
    n_periods: int
    dt_hours: float

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────────────
def _infer_dt_hours(index: pd.DatetimeIndex) -> float:
    """Deduce la resolución (1.0 h o 0.25 h) a partir de los timestamps."""
    if len(index) < 2:
        return 1.0
    step = pd.Series(index).diff().dropna().mode().iloc[0]
    return step.total_seconds() / 3600.0


def _prep_prices(prices: pd.Series) -> tuple[np.ndarray, float, pd.DatetimeIndex]:
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise TypeError("prices debe tener un DatetimeIndex")
    prices = prices.sort_index().astype(float)
    if prices.isna().any():
        raise ValueError("Hay precios vacíos (NaN) en el día")
    return prices.to_numpy(), _infer_dt_hours(prices.index), prices.index


def _summarise(date, method, p, charge, discharge, dt, bp: BatteryParams) -> DailyResult:
    e_ch = float(charge.sum() * dt)
    e_dis = float(discharge.sum() * dt)
    cost = float((p * charge).sum() * dt)
    income = float((p * discharge).sum() * dt)
    revenue = income - cost - bp.degradation_eur_mwh * e_dis
    return DailyResult(
        date=str(date),
        method=method,
        revenue_eur=round(revenue, 2),
        revenue_eur_per_mw=round(revenue / bp.power_mw, 2),
        energy_charged_mwh=round(e_ch, 3),
        energy_discharged_mwh=round(e_dis, 3),
        cycles=round(e_dis / bp.usable_mwh, 3) if bp.usable_mwh else 0.0,
        avg_charge_price=round(cost / e_ch, 2) if e_ch > 1e-9 else float("nan"),
        avg_discharge_price=round(income / e_dis, 2) if e_dis > 1e-9 else float("nan"),
        spread_max_min=round(float(p.max() - p.min()), 2),
        n_periods=len(p),
        dt_hours=dt,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Método 1 — heurística simple (screening, cota superior)
# ─────────────────────────────────────────────────────────────────────────────
def arbitrage_simple(prices: pd.Series, bp: BatteryParams) -> tuple[DailyResult, pd.DataFrame]:
    """
    Cota superior del arbitraje: resuelve de forma exacta el problema de
    `arbitrage_optimal` SIN el orden temporal (sin dinámica de SoC periodo a
    periodo). Mantiene potencia máxima, pérdidas (descarga ≤ rte · carga),
    degradación y el límite de `max_cycles_per_day`. Al ser una relajación del
    problema óptimo, su ingreso es siempre ≥ el de `arbitrage_optimal`.

    Algoritmo voraz (exacto para esta relajación):
      1. Con precio negativo se carga siempre a potencia nominal (cobra por
         consumir); esa energía queda disponible "gratis" para vender.
      2. Se descarga en los periodos más caros mientras compense la
         degradación, usando primero la energía gratuita y después la
         comprada en los periodos más baratos, si  p_venta − degradación −
         p_compra/rte > 0. Todo ello hasta agotar ciclos o potencia.
    El programa resultante NO es operable (puede vender antes de comprar).
    """
    bp.validate()
    p, dt, idx = _prep_prices(prices)

    cap = bp.power_mw * dt                            # MWh por periodo a potencia nominal
    neg = p < 0
    e_charge = np.where(neg, cap, 0.0)                # paso 1: carga en precios negativos
    e_discharge = np.zeros(len(p))
    free = bp.rte * e_charge.sum()                    # MWh vendibles sin comprar más
    ch_room = np.where(neg, 0.0, cap)                 # capacidad de carga aún libre (MWh)
    dis_left = bp.usable_mwh * bp.max_cycles_per_day  # MWh que aún se pueden descargar

    cheap = [c for c in np.argsort(p, kind="stable") if not neg[c]]
    ci = 0
    for d in np.argsort(-p, kind="stable"):           # paso 2: del más caro al más barato
        if dis_left <= 1e-12 or p[d] - bp.degradation_eur_mwh <= 0:
            break
        room = cap
        x = min(room, free, dis_left)                 # primero, energía gratuita
        e_discharge[d] += x
        free -= x
        dis_left -= x
        room -= x
        while room > 1e-12 and dis_left > 1e-12 and ci < len(cheap):
            c = cheap[ci]
            # ¿Compensa? cada MWh vendido exige comprar 1/rte MWh
            if p[d] - bp.degradation_eur_mwh - p[c] / bp.rte <= 0:
                break
            x = min(room, ch_room[c] * bp.rte, dis_left)
            e_discharge[d] += x
            e_charge[c] += x / bp.rte
            ch_room[c] -= x / bp.rte
            dis_left -= x
            room -= x
            if ch_room[c] <= 1e-12:
                ci += 1

    charge = e_charge / dt
    discharge = e_discharge / dt

    schedule = pd.DataFrame(
        {"price": p, "charge_mw": charge, "discharge_mw": discharge}, index=idx
    )
    res = _summarise(idx[0].date(), "simple", p, charge, discharge, dt, bp)
    return res, schedule


# ─────────────────────────────────────────────────────────────────────────────
# Método 2 — optimización lineal (la buena)
# ─────────────────────────────────────────────────────────────────────────────
def arbitrage_optimal(
    prices: pd.Series,
    bp: BatteryParams,
    forbid_simultaneous: bool = True,
) -> tuple[DailyResult, pd.DataFrame]:
    """
    Maximiza  Σ p_t·(d_t − c_t)·dt − deg·Σ d_t·dt
    sujeto a:
        0 ≤ c_t, d_t ≤ P
        SoC_t = SoC_{t-1} + η_c·c_t·dt − d_t·dt/η_d
        SoC_min ≤ SoC_t ≤ SoC_max
        SoC_T = SoC_0                               (el día empieza y acaba igual)
        Σ d_t·dt ≤ ciclos · E_útil
    Variables: [c_0..c_{T-1}, d_0..d_{T-1}, s_0..s_{T-1}]
    """
    bp.validate()
    p, dt, idx = _prep_prices(prices)
    T = len(p)
    eta_c = eta_d = np.sqrt(bp.rte)
    E = bp.energy_mwh
    s0 = bp.soc_initial * E

    # Objetivo (linprog minimiza → cambiamos signo)
    eps = 1e-3 if forbid_simultaneous else 0.0   # penaliza mover energía sin sentido
    cost_c = p * dt + eps
    cost_d = -(p - bp.degradation_eur_mwh) * dt + eps
    cost_s = np.zeros(T)
    c_vec = np.concatenate([cost_c, cost_d, cost_s])

    # Igualdades: dinámica de SoC  →  s_t − s_{t-1} − η_c·dt·c_t + dt/η_d·d_t = 0
    A_eq = np.zeros((T + 1, 3 * T))
    b_eq = np.zeros(T + 1)
    for t in range(T):
        A_eq[t, t] = -eta_c * dt            # c_t
        A_eq[t, T + t] = dt / eta_d         # d_t
        A_eq[t, 2 * T + t] = 1.0            # s_t
        if t == 0:
            b_eq[t] = s0
        else:
            A_eq[t, 2 * T + t - 1] = -1.0   # −s_{t-1}
    # SoC final = SoC inicial
    A_eq[T, 2 * T + T - 1] = 1.0
    b_eq[T] = s0

    # Desigualdad: límite de ciclos diarios
    A_ub = np.zeros((1, 3 * T))
    A_ub[0, T:2 * T] = dt
    b_ub = np.array([bp.max_cycles_per_day * bp.usable_mwh])

    bounds = (
        [(0, bp.power_mw)] * T
        + [(0, bp.power_mw)] * T
        + [(bp.soc_min * E, bp.soc_max * E)] * T
    )

    sol = linprog(c_vec, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=bounds, method="highs")
    if not sol.success:
        raise RuntimeError(f"Optimización fallida para {idx[0].date()}: {sol.message}")

    x = sol.x
    charge = np.clip(x[:T], 0, None)
    discharge = np.clip(x[T:2 * T], 0, None)
    soc = x[2 * T:]
    # Limpieza de ruido numérico
    charge[charge < 1e-6] = 0.0
    discharge[discharge < 1e-6] = 0.0

    schedule = pd.DataFrame(
        {"price": p, "charge_mw": charge, "discharge_mw": discharge,
         "soc_mwh": soc, "soc_pct": soc / E * 100},
        index=idx,
    )
    res = _summarise(idx[0].date(), "optimal", p, charge, discharge, dt, bp)
    return res, schedule


# ─────────────────────────────────────────────────────────────────────────────
# Ejecución para un periodo (→ tabla bess_daily)
# ─────────────────────────────────────────────────────────────────────────────
def run_period(
    prices: pd.Series,
    bp: BatteryParams,
    method: str = "optimal",
    tz: str = "Europe/Madrid",
) -> pd.DataFrame:
    """
    Calcula el arbitraje día a día sobre una serie larga de precios.
    `prices`: Serie €/MWh con DatetimeIndex (naive se asume hora local de Madrid).
    Devuelve un DataFrame con una fila por día (formato tabla `bess_daily`).
    """
    fn = {"optimal": arbitrage_optimal, "simple": arbitrage_simple}[method]
    s = prices.sort_index()
    if s.index.tz is None:
        s = s.tz_localize(tz, ambiguous="infer", nonexistent="shift_forward")
    else:
        s = s.tz_convert(tz)

    rows = []
    for day, day_prices in s.groupby(s.index.date):
        if len(day_prices) < 20:           # día incompleto → se omite
            continue
        res, _ = fn(day_prices, bp)
        d = res.to_dict()
        d["duration_h"] = bp.duration_h
        d["rte"] = bp.rte
        rows.append(d)
    return pd.DataFrame(rows)


def annual_summary(daily: pd.DataFrame) -> dict:
    """KPIs para la calculadora de la web."""
    if daily.empty:
        return {}
    days = len(daily)
    return {
        "days": days,
        "revenue_eur_per_mw_total": float(round(daily["revenue_eur_per_mw"].sum(), 0)),
        "revenue_eur_per_mw_year_equiv": float(round(daily["revenue_eur_per_mw"].sum() * 365 / days, 0)),
        "avg_daily_eur_per_mw": float(round(daily["revenue_eur_per_mw"].mean(), 1)),
        "avg_cycles_per_day": float(round(daily["cycles"].mean(), 2)),
        "avg_spread_max_min": float(round(daily["spread_max_min"].mean(), 1)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Demo con una curva sintética "tipo España" (curva de pato)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    hours = np.arange(24)
    duck = np.array([75, 70, 65, 62, 63, 70, 85, 95, 60, 25, 8, 2,
                     0, -1, 0, 5, 20, 55, 95, 130, 140, 120, 100, 85], dtype=float)
    idx = pd.date_range("2026-04-15", periods=24, freq="h")
    prices = pd.Series(duck, index=idx, name="price_eur_mwh")

    for dur in (1, 2, 4):
        bp = BatteryParams(power_mw=1, energy_mwh=dur, rte=0.88, max_cycles_per_day=1.5)
        r_s, _ = arbitrage_simple(prices, bp)
        r_o, sched = arbitrage_optimal(prices, bp)
        print(f"\nBatería 1 MW / {dur} MWh")
        print(f"  simple : {r_s.revenue_eur_per_mw:8.1f} €/MW·día  ciclos={r_s.cycles}")
        print(f"  óptimo : {r_o.revenue_eur_per_mw:8.1f} €/MW·día  ciclos={r_o.cycles}  "
              f"compra media={r_o.avg_charge_price}  venta media={r_o.avg_discharge_price}")

    print("\nPrograma óptimo 1 MW / 2 MWh:")
    bp = BatteryParams(power_mw=1, energy_mwh=2, rte=0.88, max_cycles_per_day=1.5)
    _, sched = arbitrage_optimal(prices, bp)
    print(sched.round(2).to_string())

    # Prueba cuartohoraria (96 periodos)
    idx15 = pd.date_range("2026-04-15", periods=96, freq="15min")
    prices15 = pd.Series(np.repeat(duck, 4), index=idx15)
    r15, _ = arbitrage_optimal(prices15, bp)
    print(f"\n15-min: {r15.revenue_eur_per_mw} €/MW·día (debe ≈ horario)")
