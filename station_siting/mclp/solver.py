"""Maximal Covering Location Problem with substation capacity constraint (model 2.5) - SciPy MILP (HiGHS).

max  sum_h D_h y_h + eps * sum_j score_j x_j
s.t. y_h <= sum_{j covers h} x_j        (hexagon counted only if a chosen site is within the radius)
     sum_j x_j  = N (no grid limit)  or  <= N (with grid limit: the grid may host fewer)
     sum_{j at substation s} P x_j <= C_s   (EV allowance of substation s, MW)
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.spatial import cKDTree


def coverage_sets(site_xy: np.ndarray, hex_xy: np.ndarray, radius_m: float) -> list[list[int]]:
    return cKDTree(hex_xy).query_ball_point(site_xy, r=radius_m)


def solve(D: np.ndarray, cover: list[list[int]], n_sites: int, score: np.ndarray, site_gss: np.ndarray | None = None,
          allowance_mw: dict[str, float] | None = None, station_mw: float | None = None, eps: float = 1e-3,
          time_limit: float = 60) -> dict:
    nJ, nH = len(cover), len(D)
    c = np.r_[-eps * np.asarray(score, float), -np.asarray(D, float)]
    r, cc, v = [], [], []
    for j, hs in enumerate(cover):
        r += list(hs); cc += [j] * len(hs); v += [-1.0] * len(hs)
    r += list(range(nH)); cc += [nJ + h for h in range(nH)]; v += [1.0] * nH
    grid = station_mw is not None and allowance_mw is not None and site_gss is not None
    cons = [LinearConstraint(sparse.csr_matrix((v, (r, cc)), shape=(nH, nJ + nH)), -np.inf, 0),
            LinearConstraint(np.r_[np.ones(nJ), np.zeros(nH)][None, :], 0 if grid else n_sites, n_sites)]
    if grid:
        names = sorted(set(site_gss))
        idx = {s: i for i, s in enumerate(names)}
        rows = sparse.lil_matrix((len(names), nJ + nH))
        for j, s in enumerate(site_gss):
            rows[idx[s], j] = station_mw
        cons.append(LinearConstraint(rows.tocsr(), -np.inf, np.array([allowance_mw.get(s, 0.0) for s in names])))
    t = time.time()
    res = milp(c, constraints=cons, integrality=np.r_[np.ones(nJ), np.zeros(nH)], bounds=Bounds(0, 1),
               options={"time_limit": time_limit, "mip_rel_gap": 1e-3})
    sel = np.flatnonzero(res.x[:nJ] > 0.5) if res.x is not None else np.array([], dtype=int)
    return {"selected": sel, "status": int(res.status), "message": res.message, "runtime_s": round(time.time() - t, 3)}


def evaluate(sel_xy: np.ndarray, hexes: pd.DataFrame, radius_m: float, demand_cols: list[str],
             gss_of_sel=None, allowance_mw: dict[str, float] | None = None, station_mw: float | None = None) -> dict:
    covered = np.zeros(len(hexes), bool)
    if len(sel_xy):
        for hs in cKDTree(hexes[["x", "y"]].to_numpy()).query_ball_point(sel_xy, r=radius_m):
            covered[hs] = True
    out = {f"coverage_{c.removeprefix('D_')}_pct": float(100 * hexes[c].to_numpy()[covered].sum() / hexes[c].sum())
           for c in demand_cols}
    if gss_of_sel is not None and station_mw is not None and allowance_mw is not None:
        load = pd.Series(list(gss_of_sel)).value_counts() * station_mw
        lim = load.index.map(lambda s: allowance_mw.get(s, 0.0))
        out["grid_violations"] = int((load > lim + 1e-9).sum())
        out["grid_overload_mw"] = float((load - lim).clip(lower=0).sum())
    return out
