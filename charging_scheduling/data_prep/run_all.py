"""Run all C1 cleaning steps.  Usage (from the project root):

    python -m charging_scheduling.data_prep.run_all            # everything
    python -m charging_scheduling.data_prep.run_all --skip-recon  # skip the slow 4.5 GB smart-meter step

Reads only data/raw (never changed). Writes Parquet to data/interim + data/processed and a
cleaning report to results/data_prep_report.json.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import pandas as pd

from . import recon, sessions, urbanev
from .paths import INTERIM, PROCESSED, RAW, RESULTS

# Time-based splits (golden rule 3). Dates are UTC, 'end' exclusive. Rows outside -> 'excluded'.
SESSION_SPLITS = {
    # ACN: only the pre-COVID period is used for train/val/test (sessions collapsed from Mar 2020,
    # none in Sep-Oct 2020). Post-COVID rows stay in the file with split = 'excluded'.
    "acn": {"start": "2018-04-01", "val": "2019-08-01", "test": "2019-11-01", "end": "2020-03-01"},
    # Utrecht / Boulder: cut dates at ~70 % / ~85 % of sessions (fleet and usage grow over time).
    # Utrecht smart charging from Mar 2023 -> use flag_controlled_charging to filter if needed.
    "utrecht": {"start": "2020-08-01", "val": "2024-02-01", "test": "2024-05-22", "end": "2024-11-01"},
    "boulder": {"start": "2018-01-01", "val": "2023-04-11", "test": "2023-07-29", "end": "2023-12-02"},
}
# RECON-SL base load: ~15 months (Oct 2023 - Dec 2024) -> about 70 / 15 / 15 by time
BASELOAD_SPLIT = {"start": "2023-09-30", "val": "2024-08-01", "test": "2024-10-16", "end": "2024-12-24"}
URBANEV_SPLIT = {"start": "2022-08-31", "val": "2023-01-01", "test": "2023-02-01", "end": "2023-03-01"}


def _split_by_time(t: pd.Series, c: dict[str, str]) -> pd.Series:
    s = pd.Series("excluded", index=t.index, dtype="string")
    start, val, test, end = (pd.Timestamp(c[k], tz="UTC") for k in ("start", "val", "test", "end"))
    s[(t >= start) & (t < val)] = "train"
    s[(t >= val) & (t < test)] = "val"
    s[(t >= test) & (t < end)] = "test"
    return s


def _save(df: pd.DataFrame, path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return {"file": str(path.relative_to(path.parents[2])), "rows": len(df), "mb": round(path.stat().st_size / 1e6, 1)}


def run_sessions(report: dict) -> None:
    parts = {
        "acn": sessions.load_acn(RAW / "acn_data"),
        "utrecht": sessions.load_utrecht(RAW / "utrecht_4tu" / "202410DatasetEVOfficeParking_v0.csv"),
        "boulder": sessions.load_boulder(RAW / "boulder" / "boulder_ev_charging_sessions.csv"),
    }
    cleaned = []
    for name, df in parts.items():
        clean, log = sessions.apply_rules(df)
        report["cleaning"][f"sessions_{name}"] = log
        cleaned.append(clean)
    allsess = sessions.add_time_features(pd.concat(cleaned, ignore_index=True))
    allsess = sessions.assign_split(allsess, SESSION_SPLITS)
    allsess["flag_covid_period"] = (
        (allsess["source"] == "acn") & (allsess["arrival_utc"] >= pd.Timestamp("2020-03-01", tz="UTC"))
    )
    for c in ["flag_shared_id", "flag_controlled_charging"]:
        allsess[c] = allsess[c].astype("boolean").fillna(False)
    report["outputs"]["ev_sessions"] = _save(allsess, PROCESSED / "ev_sessions_clean.parquet")
    report["split_counts"]["ev_sessions"] = (
        allsess.groupby(["source", "split"]).size().unstack(fill_value=0).to_dict(orient="index")
    )
    # per-user table for routine learning / need prediction (users with an ID only)
    users = (
        allsess[allsess["user_id"].notna() & ~allsess["flag_shared_id"]]
        .groupby(["source", "user_id"])
        .agg(n_sessions=("session_id", "size"), first=("arrival_utc", "min"), last=("arrival_utc", "max"),
             mean_kwh=("kwh", "mean"), mean_stay_h=("stay_h", "mean"))
        .reset_index()
    )
    users["has_10_plus_sessions"] = users["n_sessions"] >= 10  # cold-start threshold (CLAUDE.md)
    report["outputs"]["ev_users"] = _save(users, PROCESSED / "ev_users_summary.parquet")


def run_recon(report: dict) -> None:
    files = sorted((RAW / "recon_sl/consumption_data/smart_meter/15min_interval").glob("smart_15min_*.csv"))
    readings = pd.concat([recon.read_15min_file(f) for f in files], ignore_index=True)
    intervals, log = recon.readings_to_intervals(readings)
    del readings
    report["cleaning"]["recon_15min"] = log
    report["outputs"]["recon_household_15min"] = _save(intervals, INTERIM / "recon_household_15min.parquet")
    base = recon.build_baseload(intervals)
    base["split"] = _split_by_time(base["interval_start_utc"], BASELOAD_SPLIT)
    report["outputs"]["recon_baseload_15min"] = _save(base, PROCESSED / "recon_baseload_15min.parquet")
    report["split_counts"]["recon_baseload_15min"] = base["split"].value_counts().to_dict()
    report["notes"].append(
        f"RECON-SL: {intervals['household_id'].nunique()} households with valid 15-min intervals; "
        f"base load slots need >= 50 households."
    )


def run_recon_monthly(report: dict) -> None:
    m, log = recon.clean_monthly(RAW / "recon_sl/consumption_data/non_smart_meter/monthly_consumption.csv")
    report["cleaning"]["recon_monthly"] = log
    report["outputs"]["recon_monthly"] = _save(m, PROCESSED / "recon_monthly_clean.parquet")


def run_urbanev(report: dict) -> None:
    long, zones, log = urbanev.load_zone_hourly(RAW / "urbanev" / "UrbanEVDataset.zip")
    long["split"] = _split_by_time(long["hour_start_utc"], URBANEV_SPLIT)
    report["cleaning"]["urbanev_zone_hourly"] = log
    report["outputs"]["urbanev_zone_hourly"] = _save(long, PROCESSED / "urbanev_zone_hourly.parquet")
    report["outputs"]["urbanev_zone_info"] = _save(zones, PROCESSED / "urbanev_zone_info.parquet")
    report["split_counts"]["urbanev_zone_hourly"] = long["split"].value_counts().to_dict()
    report["notes"].append("UrbanEV: zip has no weather file (README mentions one); 'occupancy' values look like "
                           "counts of busy piles, not % as the README says - check before use.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-recon", action="store_true", help="skip the slow RECON-SL 15-min step")
    a = ap.parse_args()
    report = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "cleaning": {}, "outputs": {}, "split_counts": {}, "notes": [],
              "splits": {"sessions": SESSION_SPLITS, "recon_baseload": BASELOAD_SPLIT, "urbanev": URBANEV_SPLIT}}
    steps = [("sessions", run_sessions), ("recon_monthly", run_recon_monthly), ("urbanev", run_urbanev)]
    if not a.skip_recon:
        steps.append(("recon_15min", run_recon))
    for name, fn in steps:
        t0 = time.time()
        print(f"[{name}] running ...", flush=True)
        fn(report)
        print(f"[{name}] done in {time.time() - t0:.0f} s", flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "data_prep_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({k: report[k] for k in ("cleaning", "outputs", "split_counts", "notes")}, indent=1, default=str))


if __name__ == "__main__":
    main()
