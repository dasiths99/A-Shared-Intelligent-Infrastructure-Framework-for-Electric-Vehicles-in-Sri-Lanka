"""Run all C3 cleaning steps.  Usage (from the project root, geo environment):

    python -m route_recommendation.data_prep.run_all            # everything (eVED step ~ several minutes)
    python -m route_recommendation.data_prep.run_all --skip-eved

Reads only raw files (route_recommendation/data/raw + shared/data/raw) - never changed.
Writes Parquet to route_recommendation/data/interim + processed and results/data_prep_report.json.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import pandas as pd

from . import bmw, eved, other, segments
from .paths import (BMW_DIR, BMW_SIM_DIR, DEM_DIR, EVED_BLOB, EVED_GIT_DIR, EVED_ZIP, INTERIM, OPEN_EV_JSON,
                    PROCESSED, RESULTS, VED_STATIC_EV, WEATHER_DIR)


def _save(df: pd.DataFrame, path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False) if path.suffix == ".parquet" else df.to_csv(path, index=False)
    return {"file": f"{path.parent.name}/{path.name}", "rows": len(df), "mb": round(path.stat().st_size / 1e6, 2)}


def run_bmw(rep: dict) -> pd.DataFrame:
    rows, info = bmw.load_all_trips(BMW_DIR)
    ov = bmw.read_overview(BMW_DIR / "Overview.xlsx")
    ts = segments.resample_1hz(rows)
    ts = segments.add_distance(ts)
    ts["elev_smooth_m"] = segments.smooth_elevation(ts, "elevation_m", window_m=100)
    # trip summary: measured kWh from V*I (charging removed), distance from speed
    g = ts.groupby("trip_id")
    summ = pd.DataFrame({
        "distance_km": g["dist_m"].max() / 1000, "duration_min": (g["t_s"].max() - g["t_s"].min()) / 60,
        "energy_kwh": g.apply(lambda x: (x["battery_kw"] * x["dt_s"]).sum() / 3600, include_groups=False),
        "soc_start": g["soc_pct"].first(), "soc_end": g["soc_pct"].last(),
        "ambient_c": g["ambient_c"].mean(), "heater_kwh": g.apply(
            lambda x: (x["heater_kw"].fillna(0) * x["dt_s"]).sum() / 3600, include_groups=False),
        "elev_min_m": g["elev_smooth_m"].min(), "elev_max_m": g["elev_smooth_m"].max(),
    }).reset_index()
    summ["kwh_per_100km"] = 100 * summ["energy_kwh"] / summ["distance_km"]
    summ = ov.merge(summ, on="trip_id", how="right").merge(info, on="trip_id")
    summ["has_charging_stop"] = summ["charging_s"] > 0
    summ["split"] = segments.split_within_groups(summ, "season", "start_utc")
    ts = ts.merge(summ[["trip_id", "season", "split"]], on="trip_id")
    seg = segments.make_segments(ts, "elev_smooth_m", mean_cols=("ambient_c", "heater_kw", "ac_kw", "battery_temp_c"))
    seg = seg.merge(summ[["trip_id", "season", "route", "split"]], on="trip_id")
    seg["vehicle"] = "BMW i3 60Ah"
    rep["cleaning"]["bmw_trips"] = {
        "rows_10hz": int(info["rows_10hz"].sum()), "charging_removed_s": float(info["charging_s"].sum()),
        "trips_with_charging": info.loc[info["charging_s"] > 0, "trip_id"].tolist(),
        "rows_no_battery_data": int(info["rows_no_battery_data"].sum()),
        "soc_glitch_rows": int(info["soc_glitch_rows"].sum()),
        "soc_missing_pct_mean_per_trip": round(float(info["soc_missing_pct"].mean()), 2),
        "trips_with_soc_gaps_over_10pct": info.loc[info["soc_missing_pct"] > 10, "trip_id"].tolist()}
    rep["outputs"]["bmw_trips_1hz"] = _save(ts, PROCESSED / "bmw_trips_1hz.parquet")
    rep["outputs"]["bmw_trip_summary"] = _save(summ, PROCESSED / "bmw_trip_summary.parquet")
    rep["outputs"]["bmw_segments_200m"] = _save(seg, PROCESSED / "bmw_segments_200m.parquet")
    rep["summary"]["bmw"] = {
        "trips": len(summ), "km": round(summ["distance_km"].sum(), 1), "kwh": round(summ["energy_kwh"].sum(), 1),
        "kwh_per_100km_by_season": summ.groupby("season")["kwh_per_100km"].median().round(1).to_dict(),
        "segments": len(seg), "segments_with_gap": int(seg["has_gap"].sum()),
        "split_trips": summ.groupby(["season", "split"]).size().unstack(fill_value=0).to_dict(orient="index"),
        "split_segments": seg["split"].value_counts().to_dict(),
        "grade_pct_p1_p99": seg["grade_pct"].quantile([0.01, 0.99]).round(2).tolist(),
    }
    return summ


def run_bmw_sim(rep: dict) -> pd.DataFrame:
    sim = pd.concat([bmw.read_sim(f) for f in sorted(BMW_SIM_DIR.glob("*.csv"))], ignore_index=True)
    rep["outputs"]["bmw_sim_runs"] = _save(sim, PROCESSED / "bmw_sim_runs.parquet")
    rep["summary"]["bmw_sim"] = {"runs": int(sim["scenario"].nunique()), "rows": len(sim)}
    rep["notes"].append("BMW simulation = model output: use only for physics checks / parameters, never accuracy.")
    return sim


def run_eved(rep: dict) -> None:
    eved.extract_zip_from_git(EVED_GIT_DIR, EVED_BLOB, EVED_ZIP)
    static = pd.read_excel(VED_STATIC_EV)
    rows, log = eved.read_ev_rows(EVED_ZIP, set(static["VehId"].astype(int)))
    rows, log2 = eved.clean(rows, static)
    rep["cleaning"]["eved"] = log | log2
    rep["outputs"]["eved_ev_phev_rows"] = _save(rows, INTERIM / "eved_ev_phev_rows.parquet")
    trips = eved.trip_table(rows)
    trips["split"] = eved.split_by_time(trips["start_utc"])
    for c in ("engine_on", "intersection", "bus_stop", "focus_point"):
        rows[c] = rows[c].astype("int8")
    ts = segments.resample_1hz(rows.drop(columns=["trip_start_utc", "engine_type"]))
    ts["engine_on"] = (ts["engine_on"] > 0).astype("int8")
    ts = segments.add_distance(ts)
    ts = ts.merge(trips[["trip_id", "engine_type", "split"]], on="trip_id")
    seg = segments.make_segments(ts, "elev_smooth_m", mean_cols=("ambient_c", "heater_kw", "ac_kw", "speed_limit_kmh"),
                                 sum_cols=("engine_on", "intersection", "bus_stop"))
    seg = seg.merge(trips[["trip_id", "veh_id", "engine_type", "start_utc", "split"]], on="trip_id")
    seg["electric_only"] = seg["engine_on_sum"] == 0
    rep["outputs"]["eved_trips"] = _save(trips, PROCESSED / "eved_trips.parquet")
    rep["outputs"]["eved_ev_trips_1hz"] = _save(ts, PROCESSED / "eved_ev_trips_1hz.parquet")
    rep["outputs"]["eved_segments_200m"] = _save(seg, PROCESSED / "eved_segments_200m.parquet")
    use = seg[seg["electric_only"]]
    rep["summary"]["eved"] = {
        "vehicles": int(trips["veh_id"].nunique()), "trips": len(trips),
        "trips_electric_only": int(trips["electric_only"].sum()),
        "segments": len(seg), "segments_electric_only": len(use),
        "segments_electric_only_by_type": use["engine_type"].value_counts().to_dict(),
        "split_segments_electric_only": use["split"].value_counts().to_dict(),
        "kwh_per_km_median_electric_only": round(float(use["kwh_per_km"].median()), 3),
    }
    rep["notes"].append("eVED time zone assumed America/Detroit; PHEV segments with engine running are flagged "
                        "(electric_only = False) - exclude them from EV energy training.")


def run_other(rep: dict, sim: pd.DataFrame) -> None:
    w, log = other.read_weather(WEATHER_DIR)
    rep["cleaning"]["weather"] = log
    rep["outputs"]["weather_hourly"] = _save(w, PROCESSED / "weather_hourly.parquet")
    rep["summary"]["weather_mean_temp_c"] = w.groupby("town")["temp_c"].mean().round(1).to_dict()
    idx = other.dem_index(DEM_DIR)
    rep["outputs"]["dem_tiles_index"] = _save(idx, PROCESSED / "dem_tiles_index.parquet")
    specs = other.open_ev_specs(OPEN_EV_JSON)
    rep["outputs"]["vehicle_specs_openev"] = _save(specs, PROCESSED / "vehicle_specs_openev.parquet")
    params = other.vehicle_params_from_data(sim, pd.read_excel(VED_STATIC_EV))
    rep["outputs"]["vehicle_params_from_data"] = _save(params, PROCESSED / "vehicle_params_from_data.csv")
    rep["notes"].append("Open EV Data is from 2020 (no BYD/MG ZS 2023+); mass, CdA, Crr for Sri Lankan models "
                        "must come from manufacturer spec sheets.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-eved", action="store_true")
    a = ap.parse_args()
    rep = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "outputs": {}, "cleaning": {},
           "summary": {}, "notes": [], "split_rule": "BMW: time order within each season 70/15/15 (by trips); "
                                                     "eVED: trip start time 70/15/15"}
    for name, fn in [("bmw", lambda: run_bmw(rep)), ("bmw_sim", lambda: run_bmw_sim(rep))]:
        t = time.time(); print(f"[{name}] ...", flush=True)
        out = fn()
        if name == "bmw_sim":
            sim = out
        print(f"   {time.time() - t:.0f} s", flush=True)
    t = time.time(); print("[other] ...", flush=True); run_other(rep, sim); print(f"   {time.time() - t:.0f} s", flush=True)
    if not a.skip_eved:
        t = time.time(); print("[eved] ...", flush=True); run_eved(rep); print(f"   {time.time() - t:.0f} s", flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "data_prep_report.json").write_text(json.dumps(rep, indent=2, default=str))
    print(json.dumps({k: rep[k] for k in ("summary", "cleaning", "notes")}, indent=1, default=str))


if __name__ == "__main__":
    main()
