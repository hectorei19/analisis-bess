"""Utilidades compartidas por los tests."""

from pathlib import Path

import numpy as np
import pandas as pd

FIXTURES = Path(__file__).parent / "fixtures"


def omie_fixture_days() -> dict[str, pd.Series]:
    """
    Precios ES de los ficheros OMIE reales de tests/fixtures, con índice local
    ingenuo (sin zona horaria). Lectura mínima e independiente de src/ingest,
    solo para alimentar los tests del módulo de arbitraje.
    """
    out = {}
    for f in sorted(FIXTURES.glob("marginalpdbc_*.1")):
        rows = [line.split(";") for line in f.read_text().splitlines() if line[:2] == "20"]
        p = np.array([float(r[5]) for r in rows])
        freq = "15min" if len(p) > 25 else "h"
        day = f.name[13:21]
        out[day] = pd.Series(p, index=pd.date_range(day, periods=len(p), freq=freq))
    return out
