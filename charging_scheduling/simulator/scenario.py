"""EV data simulator (model 1.5) - SCENARIOS AND DEMOS ONLY, never for model accuracy (golden rule 2).

Home-charging sessions for a Colombo feeder: arrival ~ N(18.5 h, 1.2 h), departure ~ N(7.25 h, 0.6 h) next day,
energy sampled from real session kWh values (passed in), clipped 2-25 kWh.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..scheduler import lp


def simulate_sessions(n_ev: int, real_kwh: np.ndarray, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    return {"arr_h": np.clip(rng.normal(18.5, 1.2, n_ev), 16, 22.5),
            "dep_h": np.clip(rng.normal(7.25, 0.6, n_ev), 5.5, 9.5) + 24,
            "need": np.clip(rng.choice(real_kwh, n_ev), 2, 25),
            "delay": rng.integers(0, 9, n_ev)}


def run_scenario(base_household_kw: np.ndarray, n_homes: int, n_ev: int, real_kwh: np.ndarray, seed: int,
                 pmax: float = 7.4, default_departure_h: float = 8.0) -> dict:
    """96 slots from 12:00 to 12:00 next day. Returns load curves + metrics for B1-B4 and coordinated."""
    T = 96
    hours = 12 + np.arange(T) * 0.25
    L = np.asarray(base_household_kw, float) * n_homes
    s = simulate_sessions(n_ev, real_kwh, seed)
    to_slot = lambda h: np.clip(np.ceil((np.asarray(h) - 12) * 4).astype(int), 0, T)
    a_s = to_slot(s["arr_h"])
    d_s = np.clip(np.floor((s["dep_h"] - 12) * 4).astype(int), 0, T)
    need = np.minimum(s["need"], (d_s - a_s) * pmax * lp.SLOT_H)
    tou = to_slot(np.full(n_ev, 22.5))
    strat = {
        "B1 uncontrolled": lp.greedy(a_s, d_s, need, pmax, T),
        "B2 fixed TOU 22:30": lp.greedy(np.maximum(a_s, tou), d_s, need, pmax, T),
        "B3 TOU + random delay": lp.greedy(np.maximum(a_s, tou + s["delay"]), d_s, need, pmax, T),
    }
    d_def = np.maximum(np.full(n_ev, to_slot([default_departure_h + 24])[0]), a_s + 1)
    n_def = np.minimum(np.full(n_ev, np.median(need)), (d_def - a_s) * pmax * lp.SLOT_H)
    p4 = lp.schedule_lp(L, a_s, d_def, n_def, pmax)
    p4[np.arange(T)[None, :] >= d_s[:, None]] = 0  # car really leaves at its own time
    strat["B4 coordinated, defaults"] = p4
    strat["Coordinated (personal)"] = lp.schedule_lp(L, a_s, d_s, need, pmax)
    price = lp.tou_price(hours)
    curves, metrics = {}, {}
    peak_b1 = None
    for name, p in strat.items():
        total = L + p.sum(axis=0)
        delivered = (p * lp.SLOT_H).sum(axis=1)
        peak_b1 = peak_b1 or total.max()
        curves[name] = np.round(total, 2).tolist()
        metrics[name] = {"peak_kw": round(float(total.max()), 1),
                         "peak_reduction_vs_B1_pct": round(100 * (1 - total.max() / peak_b1), 1),
                         "par": round(float(total.max() / total.mean()), 3),
                         "car_ready_pct": round(100 * float(np.mean(delivered >= 0.99 * need)), 1),
                         "ev_cost_lkr_per_car": round(float((p * lp.SLOT_H * price).sum() / n_ev), 1)}
    labels = pd.date_range("2000-01-01 12:00", periods=T, freq="15min").strftime("%H:%M").tolist()
    return {"time_local": labels, "base_kw": np.round(L, 2).tolist(), "curves": curves, "metrics": metrics,
            "note": "Scenario with SIMULATED home-charging sessions - not a model-accuracy test."}
