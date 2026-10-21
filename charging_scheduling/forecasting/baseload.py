"""Day-ahead base-load forecast (model 1.1a) - features shared by training notebook and backend.

Every feature is at least 24 h old (lag >= 96 slots), so a forecast for day D can be made at midnight.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LAGS = (96, 192, 288, 672, 1344)
FEATS = ["slot", "weekday", "is_weekend", "month", *[f"lag_{L}" for L in LAGS], "mean_prev_day", "mean_same_slot_4w"]


def make_features(s: pd.Series, tz: str = "Asia/Colombo") -> pd.DataFrame:
    df = pd.DataFrame({"y": s})
    local = df.index.tz_convert(tz)
    df["slot"] = local.hour * 4 + local.minute // 15
    df["weekday"] = local.dayofweek
    df["is_weekend"] = (local.dayofweek >= 5).astype(int)
    df["month"] = local.month
    for lag in LAGS:
        df[f"lag_{lag}"] = s.shift(lag)
    df["mean_prev_day"] = s.shift(96).rolling(96, min_periods=80).mean()
    df["mean_same_slot_4w"] = pd.concat([s.shift(672 * k) for k in (1, 2, 3, 4)], axis=1).mean(axis=1)
    return df


def load_series(processed_dir: Path) -> pd.Series:
    """Average kW per household per 15-min slot (UTC index, regular grid, gaps = NaN)."""
    b = pd.read_parquet(processed_dir / "recon_baseload_15min.parquet")
    return b.set_index("interval_start_utc")["mean_kw"].asfreq("15min")


def typical_profile(s: pd.Series, tz: str = "Asia/Colombo") -> pd.DataFrame:
    """Typical kW per household by weekday x slot of day (used to plan 'tonight' when no fresh data)."""
    local = s.index.tz_convert(tz)
    df = pd.DataFrame({"kw": s.values, "weekday": local.dayofweek, "slot": local.hour * 4 + local.minute // 15})
    return df.dropna().groupby(["weekday", "slot"])["kw"].mean().unstack()


def forecast_day(model, s: pd.Series, date_local: str, tz: str = "Asia/Colombo") -> pd.DataFrame:
    """Forecast vs actual vs 'same time last week' for one local day inside the data range."""
    feats = make_features(s, tz)
    start = pd.Timestamp(date_local, tz=tz).tz_convert("UTC")
    day = feats.loc[start: start + pd.Timedelta(hours=23, minutes=45)]
    if day.empty:
        raise ValueError("date outside data range")
    out = pd.DataFrame({
        "time_local": day.index.tz_convert(tz).strftime("%H:%M"),
        "actual_kw": day["y"].round(4),
        "forecast_kw": np.round(model.predict(day[FEATS]), 4),
        "last_week_kw": day["lag_672"].round(4),
    })
    return out.reset_index(drop=True)
