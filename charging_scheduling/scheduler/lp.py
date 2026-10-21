"""Charging schedulers (model 1.4) and baselines B1-B4.

* schedule_lp  - coordinated LP for many EVs: stage 1 minimise feeder peak, stage 2 fill low-load slots.
* greedy       - charge at full power from a start slot (B1 uncontrolled, B2 TOU 22:30, B3 TOU + delay).
* plan_single  - one driver's personal plan: cheapest + lowest-load slots before departure.
Slots are 15 minutes (SLOT_H = 0.25 h).
"""

from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.optimize import linprog

from shared import config

SLOT_H = 0.25


def tou_price(hours_local: np.ndarray) -> np.ndarray:
    """PUCSL domestic TOU price (LKR/kWh) for local clock hours (0-24, may exceed 24 for next day)."""
    h = np.mod(hours_local, 24)
    t = config.TOU_DOMESTIC
    return np.select([(h >= 18.5) & (h < 22.5), (h >= 5.5) & (h < 18.5)],
                     [t["peak"]["lkr_per_kwh"], t["day"]["lkr_per_kwh"]], t["offpeak"]["lkr_per_kwh"]).astype(float)


def schedule_lp(base: np.ndarray, a_s: np.ndarray, d_s: np.ndarray, need: np.ndarray, pmax: float) -> np.ndarray:
    """Return p[i, t] (kW). Each EV i charges `need` kWh between slot a_s (incl.) and d_s (excl.)."""
    n, T = len(need), len(base)
    var = [(i, t) for i in range(n) for t in range(a_s[i], d_s[i])]
    nv = len(var)
    P = nv
    rows = [t for _, t in var] + list(range(T))
    cols = list(range(nv)) + [P] * T
    vals = [1.0] * nv + [-1.0] * T
    A_ub = sparse.csr_matrix((vals, (rows, cols)), shape=(T, nv + 1))
    b_ub = -np.asarray(base, float)
    A_eq = sparse.csr_matrix((np.full(nv, SLOT_H), ([i for i, _ in var], list(range(nv)))), shape=(n, nv + 1))
    bounds = [(0, pmax)] * nv + [(0, None)]
    c1 = np.zeros(nv + 1)
    c1[P] = 1
    r1 = linprog(c1, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=need, bounds=bounds, method="highs")
    if r1.status != 0:
        raise ValueError(f"LP infeasible: {r1.message}")
    c2 = np.zeros(nv + 1)
    c2[:nv] = [base[t] for _, t in var]
    r2 = linprog(c2, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=need,
                 bounds=bounds[:-1] + [(0, r1.x[P] * (1 + 1e-6) + 1e-6)], method="highs")
    x = r2.x if r2.status == 0 else r1.x
    p = np.zeros((n, T))
    for k, (i, t) in enumerate(var):
        p[i, t] = x[k]
    return p


def greedy(start: np.ndarray, end: np.ndarray, need: np.ndarray, pmax: float, T: int) -> np.ndarray:
    p = np.zeros((len(need), T))
    for i in range(len(need)):
        left, t = need[i], start[i]
        while left > 1e-9 and t < min(end[i], T):
            e = min(pmax * SLOT_H, left)
            p[i, t] = e / SLOT_H
            left -= e
            t += 1
    return p


def plan_single(hours_local: np.ndarray, base_kw: np.ndarray, other_ev_kw: np.ndarray, need_kwh: float,
                pmax: float, a: int, d: int, load_weight: float = 20.0) -> dict:
    """Personal plan: fill the slots with the lowest (tariff + load) score between plug-in a and departure d.

    Linear cost -> filling the cheapest slots first is optimal. `load_weight` (LKR per normalised load unit)
    pushes charging away from busy slots (base load + EVs already planned by other drivers = coordination).
    """
    T = len(hours_local)
    price = tou_price(hours_local)
    load = base_kw + other_ev_kw
    norm = (load - np.nanmin(load)) / max(np.nanmax(load) - np.nanmin(load), 1e-9)
    score = price + load_weight * norm
    window = np.arange(a, min(d, T))
    order = window[np.argsort(score[window], kind="stable")]
    p = np.zeros(T)
    left = need_kwh
    for t in order:
        if left <= 1e-9:
            break
        e = min(pmax * SLOT_H, left)
        p[t] = e / SLOT_H
        left -= e
    unc = greedy(np.array([a]), np.array([d]), np.array([need_kwh]), pmax, T)[0]
    return {"p_kw": p, "uncontrolled_kw": unc, "price": price, "unmet_kwh": max(left, 0.0),
            "cost_lkr": float((p * SLOT_H * price).sum()), "uncontrolled_cost_lkr": float((unc * SLOT_H * price).sum())}


def windows(p_kw: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous charging blocks as (start_slot, end_slot_exclusive)."""
    on = np.r_[0, (p_kw > 1e-6).astype(int), 0]
    edges = np.flatnonzero(np.diff(on))
    return list(zip(edges[0::2], edges[1::2]))
