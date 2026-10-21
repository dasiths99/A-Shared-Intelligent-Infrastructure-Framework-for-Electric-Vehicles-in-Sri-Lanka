"""Weather, DEM tile index, vehicle specs (Open EV Data) and vehicle parameters found in the datasets."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

TOWNS = {"Colombo", "Kandy", "NuwaraEliya", "Galle", "Jaffna", "Kurunegala", "Kegalle", "Anuradhapura"}


def read_weather(folder: Path) -> tuple[pd.DataFrame, dict]:
    """Open-Meteo CSVs: 2-line location header, blank line, then hourly table in Asia/Colombo time."""
    parts, log = [], {}
    for f in sorted(folder.glob("*_hourly_*.csv")):
        town = f.name.split("_")[0]
        meta = pd.read_csv(f, nrows=1)
        d = pd.read_csv(f, skiprows=3)
        d.columns = ["time_local", "temp_c", "rh_pct"]
        d["time_utc"] = pd.to_datetime(d["time_local"]).dt.tz_localize("Asia/Colombo").dt.tz_convert("UTC")
        n = len(d)
        d = d.dropna(subset=["temp_c"]).drop_duplicates("time_utc")
        bad = (d["temp_c"] < -5) | (d["temp_c"] > 45) | (d["rh_pct"] < 0) | (d["rh_pct"] > 100)
        log[town] = {"rows_in": n, "removed": int(n - len(d) + bad.sum())}
        d = d[~bad]
        parts.append(d.drop(columns="time_local").assign(
            town=town, lat=float(meta["latitude"].iloc[0]), lon=float(meta["longitude"].iloc[0]),
            elevation_m=float(meta["elevation"].iloc[0])))
    return pd.concat(parts, ignore_index=True), log


def dem_index(folder: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(folder.glob("*.tif")):
        with rasterio.open(f) as r:
            b = r.bounds
            rows.append({"file": f.name, "west": b.left, "south": b.bottom, "east": b.right, "north": b.top,
                         "crs": str(r.crs), "res_deg": r.res[0], "nodata": r.nodata})
    return pd.DataFrame(rows)


def sample_elevation(index: pd.DataFrame, folder: Path, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Elevation (m) at points from the DEM tiles (helper for later route work)."""
    out = np.full(len(lon), np.nan)
    for _, t in index.iterrows():
        m = (lon >= t.west) & (lon < t.east) & (lat >= t.south) & (lat < t.north)
        if m.any():
            with rasterio.open(folder / t.file) as r:
                out[m] = [v[0] for v in r.sample(zip(lon[m], lat[m]))]
    return out


def open_ev_specs(path: Path) -> pd.DataFrame:
    d = json.loads(path.read_text(encoding="utf-8"))["data"]
    rows = []
    for v in d:
        ac, dc = v.get("ac_charger") or {}, v.get("dc_charger") or {}
        e = v.get("energy_consumption") or {}
        rows.append({
            "brand": v.get("brand"), "model": v.get("model"), "variant": v.get("variant") or None,
            "release_year": v.get("release_year"), "type": v.get("type"),
            "usable_kwh": v.get("usable_battery_size"), "max_ac_kw": ac.get("max_power"),
            "ac_ports": ";".join(ac.get("ports") or []) or None, "max_dc_kw": dc.get("max_power"),
            "dc_ports": ";".join(dc.get("ports") or []) or None,
            "kwh_per_100km": e.get("average_consumption"),
        })
    df = pd.DataFrame(rows)
    df["kwh_per_100km"] = pd.to_numeric(df["kwh_per_100km"], errors="coerce")
    df = df[df["type"] == "bev"].drop_duplicates(["brand", "model", "variant", "release_year", "usable_kwh"])
    return df.reset_index(drop=True)


def vehicle_params_from_data(sim: pd.DataFrame, ved_static: pd.DataFrame) -> pd.DataFrame:
    """Only values that are really in the data. Missing ones stay empty -> fill from spec sheets."""
    moving = sim[sim["Speed [m/s]"] > 1]
    crr = moving["Roll Resistance Coeff [-]"]
    leaf = ved_static[ved_static["EngineType"] == "EV"]["Generalized_Weight"]
    return pd.DataFrame([
        {"vehicle": "BMW i3 (60 Ah)", "parameter": "crr", "value": round(float(crr.median()), 5),
         "note": f"median of TUM simulation while moving (range {crr.min():.4f}-{crr.max():.4f}, speed-dependent)",
         "source": "TUM BMW i3 simulation"},
        {"vehicle": "BMW i3 (60 Ah)", "parameter": "rotating_mass_equiv_kg",
         "value": float(sim["Mass Jred [kg]"].dropna().iloc[0]), "note": "equivalent mass of rotating parts (not vehicle mass)",
         "source": "TUM BMW i3 simulation"},
        {"vehicle": "BMW i3 (60 Ah)", "parameter": "mass_kg", "value": None,
         "note": "NOT in data - take from BMW spec sheet", "source": "-"},
        {"vehicle": "BMW i3 (60 Ah)", "parameter": "cda_m2", "value": None,
         "note": "NOT in data - take from spec sheet / literature", "source": "-"},
        {"vehicle": "Nissan Leaf 2013 (VED EV)", "parameter": "weight_class_lb",
         "value": float(leaf.iloc[0]) if len(leaf) else None,
         "note": "VED 'generalized weight' class, not exact mass", "source": "VED static data"},
    ])
