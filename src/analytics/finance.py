"""
Retorno de la inversión de una batería (modelo anual sencillo).

Supuestos (a mostrar en la web):
  - El ingreso del año 1 es el ingreso anual equivalente del periodo analizado.
  - Cada año el ingreso baja según la degradación anual de capacidad
    (ingreso_año_n = ingreso_año_1 · (1 − degradación)^(n−1)).
  - Costes de operación (O&M) constantes cada año.
  - Sin impuestos, financiación, inflación ni sustitución de celdas.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import brentq


@dataclass
class InvestmentParams:
    capex_eur: float                  # inversión inicial total
    annual_revenue_eur: float         # ingreso del año 1
    om_eur_per_year: float = 0.0      # costes de operación anuales
    degradation: float = 0.0          # pérdida anual de ingreso (0.02 = 2 %)
    discount_rate: float = 0.0        # tasa de descuento (0.07 = 7 %)
    lifetime_years: int = 15


@dataclass
class InvestmentResult:
    cashflows: pd.DataFrame           # una fila por año (0 = inversión)
    payback_years: float | None       # None si no se recupera en la vida útil
    discounted_payback_years: float | None
    npv_eur: float
    irr: float | None                 # None si no existe (p. ej. nunca se recupera)


def _payback(cumulative: np.ndarray) -> float | None:
    """Años (con decimales) hasta que el acumulado deja de ser negativo."""
    for year in range(1, len(cumulative)):
        if cumulative[year] >= 0:
            prev = cumulative[year - 1]
            gained = cumulative[year] - prev
            return year - 1 + (-prev / gained if gained > 0 else 0.0)
    return None


def _npv(rate: float, flows: np.ndarray) -> float:
    years = np.arange(len(flows))
    return float((flows / (1 + rate) ** years).sum())


def evaluate(p: InvestmentParams) -> InvestmentResult:
    years = np.arange(p.lifetime_years + 1)
    revenue = np.where(years == 0, 0.0,
                       p.annual_revenue_eur * (1 - p.degradation) ** np.maximum(years - 1, 0))
    om = np.where(years == 0, 0.0, p.om_eur_per_year)
    capex = np.where(years == 0, p.capex_eur, 0.0)
    flow = revenue - om - capex
    discounted = flow / (1 + p.discount_rate) ** years

    df = pd.DataFrame({
        "year": years,
        "revenue_eur": revenue,
        "om_eur": om,
        "capex_eur": capex,
        "cashflow_eur": flow,
        "cumulative_eur": flow.cumsum(),
        "discounted_cumulative_eur": discounted.cumsum(),
    })

    irr = None
    if flow[1:].sum() > p.capex_eur and p.capex_eur > 0:
        irr = brentq(_npv, -0.99, 10.0, args=(flow,))

    return InvestmentResult(
        cashflows=df,
        payback_years=_payback(df["cumulative_eur"].to_numpy()),
        discounted_payback_years=_payback(df["discounted_cumulative_eur"].to_numpy()),
        npv_eur=float(discounted.sum()),
        irr=irr,
    )
