"""Shared helpers for driving time series: 1 Hz resampling and ~200 m segment table.

Sign convention everywhere: battery_kw > 0 = battery DISCHARGING (driving), < 0 = charging/regen.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEG_LEN_M = 200.0
MIN_SEG_M = 100.0  # last piece of a trip shorter than this is dropped
MAX_GAP_S = 5.0  # time gap inside a segment larger than this -> segment flagged


def resample_1hz(df: pd.DataFrame, group: str = "trip_id") -> pd.DataFrame:
    """Average all numeric columns per whole second (t_s) within each trip."""
    df = df.assign(_sec=np.floor(df["t_s"]).astype("int64"))
    num = df.select_dtypes("number").columns.difference(["_sec", "t_s"])
    out = df.groupby([group, "_sec"], sort=True)[list(num)].mean().reset_index().rename(columns={"_sec": "t_s"})
    return out


def add_distance(df: pd.DataFrame, group: str = "trip_id") -> pd.DataFrame:
    """Cumulative distance (m) from speed; dt per row (s). Gaps > MAX_GAP_S count as no movement."""
    df = df.sort_values([group, "t_s"]).copy()
    dt = df.groupby(group)["t_s"].diff().fillna(0.0)
    df["gap"] = dt > MAX_GAP_S
    df["dt_s"] = dt.where(~df["gap"], 0.0)
    v = df["speed_kmh"].fillna(0).clip(lower=0) / 3.6
    df["dist_m"] = (v * df["dt_s"]).groupby(df[group]).cumsum()
    return df


def smooth_elevation(df: pd.DataFrame, col: str, window_m: float = 100.0, group: str = "trip_id") -> pd.Series:
    """Distance-based moving average of elevation (GPS altitude is noisy and stepwise)."""
    out = pd.Series(np.nan, index=df.index)
    for _, g in df.groupby(group):
        d, z = g["dist_m"].to_numpy(), g[col].to_numpy(dtype=float)
        ok = ~np.isnan(z)
        if ok.sum() < 2:
            continue
        z = np.interp(d, d[ok], z[ok])
        cs = np.concatenate([[0], np.cumsum(z)])
        lo = np.searchsorted(d, d - window_m / 2, side="left")
        hi = np.searchsorted(d, d + window_m / 2, side="right")
        out.loc[g.index] = (cs[hi] - cs[lo]) / np.maximum(hi - lo, 1)
    return out


def make_segments(df: pd.DataFrame, elev_col: str, group: str = "trip_id",
                  mean_cols: tuple[str, ...] = (), sum_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    """Cut each trip into ~SEG_LEN_M pieces. Target = measured battery energy of the piece (kWh)."""
    df = df.copy()
    df["seg"] = (df["dist_m"] // SEG_LEN_M).astype("int64")
    e = df["battery_kw"] * df["dt_s"] / 3600
    df["e_kwh"] = e
    df["e_pos_kwh"] = e.clip(lower=0)
    df["e_regen_kwh"] = (-e).clip(lower=0)
    v = df["speed_kmh"].fillna(0)
    df["stopped"] = v < 1
    df["stop_start"] = df["stopped"] & ~df.groupby(group)["stopped"].shift(fill_value=True)
    df["stopped_dt"] = df["dt_s"].where(df["stopped"], 0.0)
    df["step_m"] = v.clip(lower=0) / 3.6 * df["dt_s"]
    df["acc_pos"] = df["accel_mps2"].clip(lower=0) if "accel_mps2" in df else np.nan
    keys = [group, "seg"]
    g = df.groupby(keys)
    seg = pd.DataFrame({
        "t_start_s": g["t_s"].min(), "duration_s": g["dt_s"].sum(),
        "dist_m": g["step_m"].sum(),
        "speed_mean_kmh": g["speed_kmh"].mean(), "speed_std_kmh": g["speed_kmh"].std(),
        "speed_max_kmh": g["speed_kmh"].max(), "n_stops": g["stop_start"].sum(), "stopped_s": g["stopped_dt"].sum(),
        "accel_pos_mean": g["acc_pos"].mean(),
        "elev_start_m": g[elev_col].first(), "elev_end_m": g[elev_col].last(),
        "energy_kwh": g["e_kwh"].sum(), "energy_traction_kwh": g["e_pos_kwh"].sum(),
        "energy_regen_kwh": g["e_regen_kwh"].sum(), "has_gap": g["gap"].any(),
    })
    for c in mean_cols:
        if c in df:
            seg[f"{c}_mean"] = g[c].mean()
    for c in sum_cols:
        if c in df:
            seg[f"{c}_sum"] = g[c].sum()
    seg = seg.reset_index()
    # segment starts where the previous one ended (same stretch of road as dist_m)
    prev_end = seg.groupby(group)["elev_end_m"].shift()
    seg["elev_start_m"] = prev_end.fillna(seg["elev_start_m"])
    seg = seg[seg["dist_m"] >= MIN_SEG_M].copy()
    seg["elev_change_m"] = seg["elev_end_m"] - seg["elev_start_m"]
    seg["grade_pct"] = 100 * seg["elev_change_m"] / seg["dist_m"]
    seg["kwh_per_km"] = seg["energy_kwh"] / (seg["dist_m"] / 1000)
    return seg.reset_index(drop=True)


def split_within_groups(order: pd.DataFrame, by: str, sort_col: str, frac=(0.70, 0.15)) -> pd.Series:
    """Time-based split inside each group (e.g. season): earliest 70 % train, next 15 % val, rest test."""
    out = pd.Series(index=order.index, dtype="string")
    for _, g in order.groupby(by):
        g = g.sort_values(sort_col)
        n = len(g)
        a, b = int(round(frac[0] * n)), int(round((frac[0] + frac[1]) * n))
        out.loc[g.index[:a]] = "train"
        out.loc[g.index[a:b]] = "val"
        out.loc[g.index[b:]] = "test"
    return out
