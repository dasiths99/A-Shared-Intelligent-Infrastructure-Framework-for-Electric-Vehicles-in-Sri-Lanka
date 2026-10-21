"""UrbanEV (Shenzhen) zone-level hourly charging data -> long table for busyness forecasting.

Read directly from the raw zip (never extracted over raw). Times are China local time
(Asia/Shanghai, UTC+8, no daylight saving) and are converted to UTC.
Note: the zip (Dryad v2026-02-04) contains no weather file although the README mentions one.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

ZONE_DIR = "UrbanEVDataset/20220901-20230228_zone-cleaned-aggregated"
METRICS = ["occupancy", "duration", "volume", "e_price", "s_price"]


def load_zone_hourly(zip_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Return (long hourly table, zone info, log). One row = one zone x one hour."""
    log: dict[str, int] = {}
    with zipfile.ZipFile(zip_path) as z:
        long = None
        for m in METRICS:
            w = pd.read_csv(z.open(f"{ZONE_DIR}/charge_1hour/{m}.csv"))
            part = w.melt(id_vars="time", var_name="zone_id", value_name=m)
            long = part if long is None else long.merge(part, on=["time", "zone_id"], how="outer")
        zones = pd.read_csv(z.open(f"{ZONE_DIR}/zone-information.csv"))
    long["zone_id"] = long["zone_id"].astype("int32")
    t = pd.to_datetime(long.pop("time"), errors="coerce")
    long["hour_start_utc"] = t.dt.tz_localize("Asia/Shanghai").dt.tz_convert("UTC")
    log["rows_in"] = len(long)
    bad = long["hour_start_utc"].isna() | long[["occupancy", "volume"]].isna().any(axis=1)
    log["missing_time_or_value"] = int(bad.sum())
    long = long[~bad]
    neg = (long[["occupancy", "duration", "volume"]] < 0).any(axis=1)
    log["negative_values"] = int(neg.sum())
    long = long[~neg]
    log["rows_out"] = len(long)
    local = long["hour_start_utc"].dt.tz_convert("Asia/Shanghai")
    long = long.assign(hour_local=local.dt.hour.astype("int8"), weekday=local.dt.dayofweek.astype("int8"))
    cols = ["zone_id", "hour_start_utc", "hour_local", "weekday", *METRICS]
    return long[cols].sort_values(["zone_id", "hour_start_utc"]).reset_index(drop=True), zones, log
