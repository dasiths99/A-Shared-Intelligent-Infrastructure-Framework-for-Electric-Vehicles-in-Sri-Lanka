"""Weighted-sum site scoring (model 2.4). Every criterion is scaled 0-1 where 1 = better."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .ahp import CRIT


def _mm(s) -> pd.Series:
    s = pd.Series(s, dtype=float)
    r = s.max() - s.min()
    return (s - s.min()) / r if r > 0 else s * 0


def criteria(c: pd.DataFrame, demand_col: str = "demand_temporal") -> pd.DataFrame:
    return pd.DataFrame({
        "demand": _mm(c[demand_col]),
        "grid": _mm(c["gss_spare_mva"].fillna(0) / (1 + c["dist_gss_m"] / 2000)),
        "road": 1 - _mm(np.log1p(c["dist_major_road_m"])),
        "land": 0.6 * _mm(np.log1p(c["site_area_m2"].fillna(0))) + 0.4 * _mm(c["commercial_share"].fillna(0)),
        "competition": _mm(np.minimum(c["dist_charger_m"], 5000)),
    }, index=c.index)


def score(c: pd.DataFrame, weights: dict[str, float], demand_col: str = "demand_temporal") -> pd.Series:
    w = pd.Series(weights)[CRIT]
    return (criteria(c, demand_col) * w).sum(axis=1)
