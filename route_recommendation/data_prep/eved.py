"""eVED (extended VED, Ann Arbor, Nov 2017 - Nov 2018): keep only the 3 EVs + 24 PHEVs.

eVED = VED signals + map-matching + smoothed elevation, gradient, speed limits, intersections, bus stops.
Read week by week straight from the zip (5.8 GB unzipped, never extracted to disk).
DayNum is the trip start (days since 2017-11-01 00:00, DayNum 1 = that midnight), Timestamp(ms) is the
offset inside the trip. Local clock assumed America/Detroit (dataset does not say) -> stored in UTC.
PHEV rows with the engine running (RPM > 0 or fuel flow > 0) are flagged; only electric-only
driving is useful for an EV energy model. Lat/lon are dropped from processed outputs (not needed).
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

KEEP = {
    "DayNum": "day_num", "VehId": "veh_id", "Trip": "trip", "Timestamp(ms)": "ts_ms",
    "Vehicle Speed[km/h]": "speed_kmh", "Engine RPM[RPM]": "engine_rpm", "Fuel Rate[L/hr]": "fuel_rate_lph",
    "MAF[g/sec]": "maf_gps", "OAT[DegC]": "ambient_c", "Air Conditioning Power[kW]": "ac_kw",
    "Air Conditioning Power[Watts]": "ac_w", "Heater Power[Watts]": "heater_w",
    "HV Battery Current[A]": "battery_a", "HV Battery SOC[%]": "soc_pct", "HV Battery Voltage[V]": "battery_v",
    "Elevation Smoothed[m]": "elev_smooth_m", "Gradient": "gradient", "Speed Limit[km/h]": "speed_limit_kmh",
    "Intersection": "intersection", "Bus Stops": "bus_stop", "Focus Points": "focus_point",
}
DAY0 = pd.Timestamp("2017-11-01")  # DayNum 1 == 2017-11-01 00:00 local


def extract_zip_from_git(git_dir: Path, blob: str, out: Path) -> None:
    """eVED.zip lives in the git object store (Windows cannot check out a file name ending in '.')."""
    if out.exists() and out.stat().st_size > 600_000_000:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        subprocess.run(["git", "-C", str(git_dir), "cat-file", "blob", blob], stdout=f, check=True)


def read_ev_rows(zip_path: Path, veh_ids: set[int], chunksize: int = 1_000_000) -> tuple[pd.DataFrame, dict]:
    parts, log = [], {"weeks": 0, "rows_scanned": 0}
    with zipfile.ZipFile(zip_path) as z:
        for name in sorted(n for n in z.namelist() if n.endswith("_week.csv")):
            log["weeks"] += 1
            # not every weekly file has every column (e.g. 'Focus Points') -> read what exists
            for ch in pd.read_csv(z.open(name), usecols=lambda c: c in KEEP, chunksize=chunksize, low_memory=False):
                log["rows_scanned"] += len(ch)
                ch = ch[ch["VehId"].isin(veh_ids)]
                if len(ch):
                    parts.append(ch.rename(columns=KEEP))
    df = pd.concat(parts, ignore_index=True)
    for c in KEEP.values():
        if c not in df:
            df[c] = np.nan
    log["rows_ev_phev"] = len(df)
    return df, log


def clean(df: pd.DataFrame, static: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    log = {"rows_in": len(df)}
    df = df.merge(static[["VehId", "EngineType", "Generalized_Weight"]].rename(
        columns={"VehId": "veh_id", "EngineType": "engine_type", "Generalized_Weight": "weight_lb"}), on="veh_id")
    df["trip_id"] = df["veh_id"].astype(int).astype(str) + "_" + df["trip"].astype(int).astype(str)
    df["t_s"] = df["ts_ms"] / 1000
    start_local = DAY0 + pd.to_timedelta(df["day_num"] - 1, unit="D")
    df["trip_start_utc"] = start_local.dt.tz_localize("America/Detroit", ambiguous="NaT",
                                                      nonexistent="NaT").dt.tz_convert("UTC")
    df["ac_kw"] = df["ac_kw"].fillna(df["ac_w"] / 1000)
    df["heater_kw"] = df["heater_w"] / 1000
    df = df.drop(columns=["ac_w", "heater_w", "trip", "ts_ms"])
    df["engine_on"] = (df["engine_rpm"].fillna(0) > 0) | (df["fuel_rate_lph"].fillna(0) > 0) | (df["maf_gps"].fillna(0) > 0)
    bad = df["battery_v"].isna() | df["battery_a"].isna() | df["speed_kmh"].isna()
    log["rows_no_battery_or_speed"] = int(bad.sum())
    df = df[~bad]
    dup = df.duplicated(["trip_id", "t_s"])
    log["duplicate_rows"] = int(dup.sum())
    df = df[~dup]
    df["battery_kw"] = -df["battery_v"] * df["battery_a"] / 1000
    impossible = df["battery_kw"].abs() > 150  # beyond any of these cars' motor/battery power
    log["impossible_power_rows"] = int(impossible.sum())
    df = df[~impossible]
    log["rows_out"] = len(df)
    log["rows_engine_on_pct"] = round(100 * df["engine_on"].mean(), 1)
    for c in ("intersection", "bus_stop", "focus_point"):
        df[c] = df[c].notna() & (df[c].astype(str) != "nan")
    return df.reset_index(drop=True), log


def trip_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("trip_id")
    t = pd.DataFrame({
        "veh_id": g["veh_id"].first(), "engine_type": g["engine_type"].first(),
        "start_utc": g["trip_start_utc"].first(), "duration_s": g["t_s"].max() - g["t_s"].min(),
        "engine_on_share": g["engine_on"].mean(), "ambient_c": g["ambient_c"].mean(),
    }).reset_index()
    t["electric_only"] = t["engine_on_share"] == 0
    return t


def split_by_time(start: pd.Series, frac=(0.70, 0.15)) -> pd.Series:
    """Chronological split on trip start: earliest 70 % train, next 15 % val, last 15 % test."""
    q1, q2 = start.quantile(frac[0]), start.quantile(frac[0] + frac[1])
    return pd.Series(np.where(start < q1, "train", np.where(start < q2, "val", "test")), index=start.index)
