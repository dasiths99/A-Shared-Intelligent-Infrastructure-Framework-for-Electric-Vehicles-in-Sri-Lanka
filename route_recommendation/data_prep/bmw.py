"""BMW i3 (60 Ah) real driving trips, TU Munich (IEEE DataPort) + the TUM simulation runs.

Raw trip files: ';' separated, Latin-1, 10 Hz, SIX different header versions -> columns are found
by name prefix. Battery current < 0 while driving, so battery_kw = -V*I/1000 (> 0 = discharge).
Fast-charging stops (B04, B09) are removed: standing still (< 1 km/h) with > 1 kW flowing INTO the battery.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

# standard name -> list of raw-header prefixes (first match wins)
COLUMN_MAP = {
    "t_s": ["Time [s]"],
    "speed_kmh": ["Velocity"],
    "elevation_m": ["Elevation"],
    "throttle_pct": ["Throttle"],
    "motor_torque_nm": ["Motor Torque"],
    "accel_mps2": ["Longitudinal Acceleration"],
    "regen_signal": ["Regenerative Braking Signal"],
    "battery_v": ["Battery Voltage"],
    "battery_a": ["Battery Current"],
    "battery_temp_c": ["Battery Temperature"],
    "soc_pct": ["SoC [%]"],
    "soc_displayed_pct": ["displayed SoC"],
    "heater_kw": ["Heating Power CAN [kW]"],
    "heater_lin_w": ["Heating Power LIN [W]"],
    "ac_kw": ["AirCon Power [kW]"],
    "ambient_c": ["Ambient Temperature ["],
    "cabin_c": ["Cabin Temperature Sensor"],
}
CHARGE_KW = 1.0


def read_trip(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=";", encoding="latin-1")
    raw.columns = [c.strip() for c in raw.columns]
    out = {}
    for std, prefixes in COLUMN_MAP.items():
        col = next((c for p in prefixes for c in raw.columns if c.startswith(p)), None)
        if col is not None:
            out[std] = pd.to_numeric(raw[col], errors="coerce")
    df = pd.DataFrame(out)
    if "heater_kw" not in df and "heater_lin_w" in df:
        df["heater_kw"] = df["heater_lin_w"] / 1000
    df = df.drop(columns=["heater_lin_w"], errors="ignore")
    df["battery_kw"] = -df["battery_v"] * df["battery_a"] / 1000
    return df


def read_overview(path: Path) -> pd.DataFrame:
    o = pd.read_excel(path)
    o = o[o["Trip"].astype(str).str.match(r"Trip[AB]\d+")].copy()
    o.columns = [str(c).strip() for c in o.columns]
    date = o["Date"].astype(str).str.strip().str.replace("_", "-", regex=False)  # two formats in the sheet
    o = pd.DataFrame({
        "trip_id": o["Trip"].str.replace("Trip", "", regex=False),
        "start_local": pd.to_datetime(date, format="%Y-%m-%d-%H-%M-%S", errors="coerce"),
        "route": o["Route/Area"], "weather": o["Weather"],
        "target_cabin_c": pd.to_numeric(o["Target Cabin Temperature"], errors="coerce"),
        "note": o.get("Note"),
    })
    o["start_utc"] = o["start_local"].dt.tz_localize("Europe/Berlin", ambiguous="NaT").dt.tz_convert("UTC")
    o["season"] = np.where(o["trip_id"].str.startswith("A"), "summer", "winter")
    return o.drop(columns="start_local").reset_index(drop=True)


def clean_trip(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remove charging rows, drop rows without battery data; returns flags for the trip summary."""
    info = {"rows_10hz": len(df)}
    charging = (df["speed_kmh"].fillna(0) < 1) & (df["battery_kw"] < -CHARGE_KW)
    info["charging_s"] = round(float(charging.sum()) / 10, 1)
    df = df[~charging]
    bad = df["battery_v"].isna() | df["battery_a"].isna() | df["t_s"].isna()
    info["rows_no_battery_data"] = int(bad.sum())
    df = df[~bad]
    glitch = df["soc_pct"] <= 0  # SoC 0 % while still driving = sensor glitch (seen at end of B14)
    info["soc_glitch_rows"] = int(glitch.sum())
    df = df.assign(soc_pct=df["soc_pct"].mask(glitch))
    info["soc_missing_pct"] = round(100 * df["soc_pct"].isna().mean(), 1)
    return df, info


def load_all_trips(folder: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (10 Hz rows of all trips with trip_id, per-trip cleaning info)."""
    parts, infos = [], []
    for f in sorted(folder.glob("Trip*.csv")):
        tid = re.sub(r"^Trip", "", f.stem)
        df, info = clean_trip(read_trip(f))
        parts.append(df.assign(trip_id=tid))
        infos.append({"trip_id": tid, **info})
    return pd.concat(parts, ignore_index=True), pd.DataFrame(infos)


# ----------------------------------------------------------------------------- simulation
SIM_RE = re.compile(r"^(Neg10|0|Pos10)_(Charging|Heating|Mixed|Standard)_(CAN|LIN)$")


def read_sim(path: Path) -> pd.DataFrame:
    """TUM simulation CSV: 2 header rows (group, signal). Keep signal names, tag the scenario."""
    raw = pd.read_csv(path, sep=";", header=[0, 1], encoding="latin-1")
    cols, group = [], ""
    for grp, sig in raw.columns:  # group label only on the first column of each group -> carry forward
        if not str(grp).startswith("Unnamed"):
            group = str(grp).strip()
        name = re.sub(r"\s+", " ", str(sig)).strip()
        cols.append(f"{group} {name}" if name == "Power [kW]" else name)  # 'Battery Power', 'Consumption Power'
    raw.columns = cols
    raw = raw.apply(pd.to_numeric, errors="coerce")
    m = SIM_RE.match(path.stem)
    temp = {"Neg10": -10, "0": 0, "Pos10": 10}[m.group(1)]
    return raw.assign(scenario=path.stem, ambient_setting_c=temp, profile=m.group(2), bus=m.group(3), is_simulation=True)
