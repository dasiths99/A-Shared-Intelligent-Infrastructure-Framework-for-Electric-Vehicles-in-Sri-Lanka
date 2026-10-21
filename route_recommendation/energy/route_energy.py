"""Energy along a route (models 3.1 + 3.2): ~200 m segments -> constant / physics / hybrid estimates.

Segment features match the C3 training notebook. Speed variation, stops and acceleration are not known on a map,
so typical values are used (same as the notebook corridor scenario) - documented assumption.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

G, RHO, SEG_LEN = 9.81, 1.2, 200.0
FEATS = ["dist_m", "duration_s", "speed_mean_kmh", "speed_std_kmh", "speed_max_kmh", "n_stops", "stopped_s",
         "acc_pos_mean", "acc_neg_mean", "elev_change_m", "grade_pct", "ambient_c_mean", "kinetic_term", "v3_term"]


def segments(length_m: np.ndarray, speed_kmh: np.ndarray, elev_from: np.ndarray, elev_to: np.ndarray,
             ambient_c: float) -> pd.DataFrame:
    cum = np.cumsum(length_m)
    seg_id = (np.r_[0, cum[:-1]] // SEG_LEN).astype(int)
    t = length_m / (speed_kmh / 3.6)
    df = pd.DataFrame({"seg": seg_id, "len": length_m, "t": t, "sp": speed_kmh, "z0": elev_from, "z1": elev_to})
    g = df.groupby("seg")
    s = pd.DataFrame({
        "dist_m": g["len"].sum(), "duration_s": g["t"].sum(),
        "speed_mean_kmh": g["len"].sum() / g["t"].sum() * 3.6,
        "speed_max_kmh": g["sp"].max() + 10, "elev_start_m": g["z0"].first(), "elev_end_m": g["z1"].last(),
    })
    s["speed_std_kmh"] = 5.0; s["n_stops"] = 0.1; s["stopped_s"] = 0.0
    s["acc_pos_mean"] = 0.15; s["acc_neg_mean"] = -0.15
    s["elev_change_m"] = s.elev_end_m - s.elev_start_m
    s["grade_pct"] = (100 * s.elev_change_m / s.dist_m).clip(-25, 25)
    s["ambient_c_mean"] = ambient_c
    v = s.speed_mean_kmh / 3.6
    th = np.arctan(s.grade_pct / 100)
    s["kinetic_term"] = G * np.sin(th) * v * s.duration_s
    s["v3_term"] = 0.5 * RHO * v ** 3 * s.duration_s
    s["x_roll"] = G * np.cos(th) * v * s.duration_s
    s["km_end"] = s.dist_m.cumsum() / 1000
    return s.reset_index(drop=True)


def physics(s: pd.DataFrame, p: dict) -> np.ndarray:
    ew = p["mass_kg"] * s.kinetic_term + p["mass_kg"] * p["crr"] * s.x_roll + p["cda_m2"] * s.v3_term
    eb = np.where(ew > 0, ew / p["eta_drive"], ew * p["eta_regen"]) / 3.6e6
    T = s.ambient_c_mean
    aux = (p["aux_base_kw"] + p["aux_cold_kw_per_C"] * np.maximum(0, 18 - T) + p["aux_hot_kw_per_C"] * np.maximum(0, T - 24)) * s.duration_s / 3600
    return np.asarray(eb + aux)


def estimate(s: pd.DataFrame, p: dict, hybrid_model, kwh_per_km_const: float | None) -> dict[str, np.ndarray]:
    ph = physics(s, p)
    out = {"physics": ph}
    if hybrid_model is not None:
        X = s[FEATS].assign(pred_physics=ph)
        out["hybrid"] = ph + hybrid_model.predict(X)
    if kwh_per_km_const:
        out["constant"] = kwh_per_km_const * s.dist_m.to_numpy() / 1000
    return out
