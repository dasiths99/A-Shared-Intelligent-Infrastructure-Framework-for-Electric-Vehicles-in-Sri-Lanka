"""Clean RECON-SL (Sri Lankan household electricity) smart-meter and monthly data.

Smart-meter files hold CUMULATIVE meter readings (importkwh, exportkwh) every 15 minutes in
Sri Lankan local time (Asia/Colombo, UTC+05:30, no daylight saving). Energy per interval is the
difference between two consecutive readings of the same meter. A reading at time t covers the
interval (t - 15 min, t], so interval_start_utc = t - 15 min (converted to UTC).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SLOT = pd.Timedelta(minutes=15)
COLOMBO_OFFSET = pd.Timedelta(hours=5, minutes=30)
MAX_KWH_PER_SLOT = 3.75  # = 15 kW average; above this is not a household load (meter catch-up/error)

USECOLS = ["household_ID", "date", "time", "importkwh(kwh)", "exportkwh(kwh)"]


def read_15min_file(path: Path, chunksize: int = 2_000_000) -> pd.DataFrame:
    """Read one 15-min file in chunks into compact columns: hh (int32), t_local, imp, exp."""
    parts = []
    for ch in pd.read_csv(path, usecols=USECOLS, chunksize=chunksize, dtype={"household_ID": "string"}):
        t = pd.to_datetime(ch["date"] + " " + ch["time"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        parts.append(pd.DataFrame({
            "hh": ch["household_ID"].str.replace("ID", "", regex=False).astype("int32"),
            "t_local": t,
            "imp": pd.to_numeric(ch["importkwh(kwh)"], errors="coerce").astype("float64"),
            "exp": pd.to_numeric(ch["exportkwh(kwh)"], errors="coerce").astype("float64"),
        }))
    return pd.concat(parts, ignore_index=True)


def readings_to_intervals(r: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Cumulative readings -> energy per 15-min interval, with quality rules.

    Keeps only differences between readings exactly 15 min apart (gaps stay missing, never
    guessed). Negative differences (meter reset/replacement) and > MAX_KWH_PER_SLOT are removed.
    """
    log = {"readings_in": len(r)}
    r = r.dropna(subset=["t_local", "imp"])
    log["readings_bad_time_or_value"] = log["readings_in"] - len(r)
    n = len(r)
    r = r.drop_duplicates(["hh", "t_local"]).sort_values(["hh", "t_local"], kind="stable")
    log["readings_duplicate"] = n - len(r)

    same_hh = r["hh"].eq(r["hh"].shift())
    step = r["t_local"].diff()
    imp_d = r["imp"].diff()
    exp_d = r["exp"].diff()
    ok_step = same_hh & step.eq(SLOT)
    log["intervals_possible"] = int(same_hh.sum())
    log["gap_not_15min"] = int((same_hh & ~step.eq(SLOT)).sum())
    neg = ok_step & ((imp_d < 0) | (exp_d < 0))
    big = ok_step & (imp_d > MAX_KWH_PER_SLOT)
    log["negative_diff_meter_reset"] = int(neg.sum())
    log["too_large_gt_15kW"] = int(big.sum())
    keep = ok_step & ~neg & ~big

    out = pd.DataFrame({
        "household_id": r["hh"][keep].to_numpy(),
        "interval_start_utc": (r["t_local"][keep] - SLOT - COLOMBO_OFFSET).dt.tz_localize("UTC").to_numpy(),
        "import_kwh": imp_d[keep].astype("float32").to_numpy(),
        "export_kwh": exp_d[keep].fillna(0).clip(lower=0).astype("float32").to_numpy(),
    })
    log["intervals_out"] = len(out)
    return out, log


def build_baseload(intervals: pd.DataFrame, min_households: int = 50) -> pd.DataFrame:
    """Average household load per 15-min slot (the 'base load' shape for C1).

    mean_kw = average power per household in that slot = mean(import_kwh) * 4.
    Slots with fewer than `min_households` meters reporting are dropped (unreliable mean).
    """
    g = intervals.groupby("interval_start_utc")["import_kwh"]
    b = pd.DataFrame({
        "mean_kw": g.mean() * 4,
        "median_kw": g.median() * 4,
        "p90_kw": g.quantile(0.9) * 4,
        "n_households": g.size(),
    }).reset_index()
    b = b[b["n_households"] >= min_households].copy()
    local = b["interval_start_utc"].dt.tz_convert("Asia/Colombo")
    b["slot_of_day"] = (local.dt.hour * 4 + local.dt.minute // 15).astype("int16")
    b["weekday"] = local.dt.dayofweek.astype("int8")
    b["is_weekend"] = b["weekday"] >= 5
    b["date_local"] = local.dt.strftime("%Y-%m-%d")
    return b.reset_index(drop=True)


def clean_monthly(path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    """Monthly bills: kWh per household per month. Drops negatives, keeps zeros (empty homes)."""
    m = pd.read_csv(path, dtype={"household_ID": "string"})
    log = {"rows_in": len(m)}
    m = m.rename(columns={"household_ID": "household_id", "consumption": "kwh"})
    m["household_id"] = m["household_id"].str.replace("ID", "", regex=False).astype("int32")
    m["month"] = pd.to_datetime(m["month"], errors="coerce").dt.to_period("M").astype("string")
    m["kwh"] = pd.to_numeric(m["kwh"], errors="coerce")
    bad = m["month"].isna() | m["kwh"].isna() | (m["kwh"] < 0)
    log["bad_rows"] = int(bad.sum())
    m = m[~bad]
    n = len(m)
    m = m.drop_duplicates(["household_id", "month"])
    log["duplicates"] = n - len(m)
    # extreme bills: > 99.9th percentile x 3 -> flag only (could be real big houses)
    lim = float(np.nanquantile(m["kwh"], 0.999)) * 3
    m["flag_extreme"] = m["kwh"] > lim
    log["flag_extreme"] = int(m["flag_extreme"].sum())
    log["rows_out"] = len(m)
    return m.reset_index(drop=True), log
