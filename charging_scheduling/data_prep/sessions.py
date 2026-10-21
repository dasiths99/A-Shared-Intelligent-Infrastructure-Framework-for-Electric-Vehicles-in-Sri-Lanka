"""Clean EV charging-session datasets (ACN, Utrecht, Boulder) into one common table.

Common output columns (one row = one charging session):
    source, site, session_id, user_id, station_id,
    arrival_utc, departure_utc, done_charging_utc, kwh, stay_h, charging_h, tz,
    arrival_hour_local, departure_hour_local, weekday, is_weekend,
    user-input columns (ACN only), quality flags, split
All times are stored in UTC (golden rule 6); `tz` keeps the local zone for features.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# Cleaning limits (documented in extra document/readme/charging_scheduling__data_prep__README.md)
MIN_STAY_H = 5 / 60  # shorter stays are plug-in tests / errors
MAX_STAY_H = 48.0  # longer stays are forgotten cars / logging errors
MAX_KWH = 100.0  # above any passenger-EV battery in these datasets
MAX_AVG_KW = 50.0  # kWh / stay above this is physically impossible for these AC sites

COMMON_COLUMNS = [
    "source", "site", "session_id", "user_id", "station_id",
    "arrival_utc", "departure_utc", "done_charging_utc", "kwh", "stay_h", "charging_h", "tz",
]

# Utrecht: IDs shared by several people (README of the 4TU dataset) -> not one person's routine
UTRECHT_SHARED_IDS = {
    "EV107", "EV191", "EV132", "EV148", "EV342", "EV242", "EV130", "EV173", "EV131", "EV384",
    "EV318", "EV127", "EV257", "EV192", "EV129", "EV211", "EV323", "EV343", "EV161", "EV456",
}
# Utrecht: smart charging (MPC) on the employee deck from March 2023, all rails except M
UTRECHT_MPC_START = pd.Timestamp("2023-03-01", tz="Europe/Amsterdam")
UTRECHT_DECK_RAILS = {"B", "C", "E", "H", "J", "K", "L"}


def _gmt(series: pd.Series) -> pd.Series:
    """Parse ACN RFC-1123 strings like 'Wed, 05 Sep 2018 11:08:09 GMT' to UTC timestamps."""
    return pd.to_datetime(series, format="%a, %d %b %Y %H:%M:%S GMT", utc=True, errors="coerce")


def load_acn(acn_dir: Path) -> pd.DataFrame:
    """Read the three ACN site files into the common schema (+ first user input)."""
    rows = []
    for f in sorted(acn_dir.glob("acn_*_sessions.json")):
        site = f.stem.replace("acn_", "").replace("_sessions", "")
        for s in json.loads(f.read_text()):
            ui = s.get("userInputs") or []
            first = ui[0] if ui else {}
            rows.append({
                "site": site,
                "session_id": s["sessionID"],
                "user_id": s.get("userID"),
                "station_id": s["stationID"],
                "arrival": s["connectionTime"],
                "departure": s["disconnectTime"],
                "done": s.get("doneChargingTime"),
                "kwh": s["kWhDelivered"],
                "tz": s.get("timezone") or "America/Los_Angeles",
                "n_user_inputs": len(ui),
                "kwh_requested": first.get("kWhRequested"),
                "requested_departure": first.get("requestedDeparture"),
                "minutes_available": first.get("minutesAvailable"),
                "miles_requested": first.get("milesRequested"),
                "wh_per_mile": first.get("WhPerMile"),
                "user_input_time": first.get("modifiedAt"),
            })
    df = pd.DataFrame(rows)
    df["source"] = "acn"
    df["arrival_utc"] = _gmt(df.pop("arrival"))
    df["departure_utc"] = _gmt(df.pop("departure"))
    df["done_charging_utc"] = _gmt(df.pop("done"))
    df["requested_departure_utc"] = _gmt(df.pop("requested_departure"))
    df["user_input_utc"] = _gmt(df.pop("user_input_time"))
    df["user_id"] = np.where(df["user_id"].notna(), "acn_" + df["user_id"].astype(str), None)
    df["charging_h"] = (df["done_charging_utc"] - df["arrival_utc"]).dt.total_seconds() / 3600
    for c in ["kwh_requested", "minutes_available", "miles_requested", "wh_per_mile"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _localize(local: pd.Series, tz: str) -> pd.Series:
    """Local wall-clock times -> UTC. Ambiguous/non-existent DST hours become NaT (dropped later)."""
    return local.dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")


def load_utrecht(csv_path: Path) -> pd.DataFrame:
    """Read Utrecht office-parking sessions (local Dutch time) into the common schema."""
    u = pd.read_csv(csv_path, sep=None, engine="python", encoding="utf-8-sig")
    tz = "Europe/Amsterdam"
    df = pd.DataFrame({
        "source": "utrecht",
        "site": "asr_utrecht",
        "user_id": "utr_" + u["EV_id_x"].astype(str),
        "station_id": u["evse_uid"].astype("string"),
        "arrival_utc": _localize(pd.to_datetime(u["start_datetime"], errors="coerce"), tz),
        "departure_utc": _localize(pd.to_datetime(u["end_datetime"], errors="coerce"), tz),
        "kwh": pd.to_numeric(u["total_energy"], errors="coerce"),
        "tz": tz,
        "rail": u["rail"].astype("string"),
        "battery_kwh_survey": pd.to_numeric(u["capacity_kwh"], errors="coerce"),
    })
    df["session_id"] = "utr_" + u.index.astype(str)
    df["done_charging_utc"] = pd.NaT
    df["charging_h"] = np.nan
    df["flag_shared_id"] = u["EV_id_x"].astype(str).isin(UTRECHT_SHARED_IDS).to_numpy()
    rail_upper = df["rail"].fillna("").str.upper().str.strip()
    df["flag_controlled_charging"] = (
        df["arrival_utc"].ge(UTRECHT_MPC_START.tz_convert("UTC")) & rail_upper.isin(UTRECHT_DECK_RAILS)
    ).fillna(False).astype(bool)
    return df


def _hms_to_hours(s: pd.Series) -> pd.Series:
    """'2:03:02' -> 2.05 hours (Boulder duration strings)."""
    return pd.to_timedelta(s, errors="coerce").dt.total_seconds() / 3600


def load_boulder(csv_path: Path) -> pd.DataFrame:
    """Read City of Boulder public sessions. Each row carries its own MDT/MST zone label."""
    b = pd.read_csv(csv_path, encoding="utf-8-sig")
    offset = {"MDT": "-06:00", "MST": "-07:00"}

    def to_utc(time_col: str, zone_col: str) -> pd.Series:
        # two formats in the file: '1/1/2018 17:49' (to May 2023) and '2023-06-02 05:23:17' (from June 2023)
        t = pd.to_datetime(b[time_col], format="%m/%d/%Y %H:%M", errors="coerce")
        iso = pd.to_datetime(b[time_col], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        t = t.fillna(iso)
        off = b[zone_col].map(offset)
        txt = t.dt.strftime("%Y-%m-%dT%H:%M:%S") + off
        return pd.to_datetime(txt, utc=True, errors="coerce")

    df = pd.DataFrame({
        "source": "boulder",
        "site": "boulder",
        "session_id": "bou_" + b["ObjectId2"].astype(str),
        "user_id": None,  # Boulder data has no driver ID
        "station_id": b["Station_Name"].astype("string"),
        "arrival_utc": to_utc("Start_Date___Time", "Start_Time_Zone"),
        "departure_utc": to_utc("End_Date___Time", "End_Time_Zone"),
        "kwh": pd.to_numeric(b["Energy__kWh_"], errors="coerce"),
        "tz": "America/Denver",
        "charging_h": _hms_to_hours(b["Charging_Time__hh_mm_ss_"]),
        "port_type": b["Port_Type"].astype("string"),
    })
    df["done_charging_utc"] = pd.NaT
    return df


def apply_rules(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply the common cleaning rules. Returns the clean table and rows removed per rule."""
    log: dict[str, int] = {"rows_in": len(df)}

    def drop(mask: pd.Series, name: str) -> None:
        nonlocal df
        log[name] = int(mask.sum())
        df = df[~mask]

    drop(df["arrival_utc"].isna() | df["departure_utc"].isna(), "missing_or_ambiguous_time")
    drop(df.duplicated(["source", "session_id"]), "duplicate_session_id")
    drop(df.duplicated(["source", "station_id", "arrival_utc", "departure_utc"]), "duplicate_station_time")
    # same session exported twice with different time precision (Boulder Jun-Aug 2023)
    minute_key = df.assign(_t=df["arrival_utc"].dt.floor("min"), _k=df["kwh"].round(3))
    drop(minute_key.duplicated(["source", "station_id", "_t", "_k"]), "duplicate_station_minute_kwh")
    df = df.assign(stay_h=(df["departure_utc"] - df["arrival_utc"]).dt.total_seconds() / 3600)
    drop(df["stay_h"] < MIN_STAY_H, "stay_too_short")
    drop(df["stay_h"] > MAX_STAY_H, "stay_too_long")
    drop(df["kwh"].isna() | (df["kwh"] <= 0), "zero_or_missing_kwh")
    drop(df["kwh"] > MAX_KWH, "kwh_too_large")
    drop(df["kwh"] / df["stay_h"] > MAX_AVG_KW, "impossible_avg_power")
    # charging time cannot be negative or longer than the stay -> set unknown, keep the session
    bad_ch = (df["charging_h"] < 0) | (df["charging_h"] > df["stay_h"] + 1 / 60)
    log["charging_h_set_missing"] = int(bad_ch.sum())
    df = df.assign(charging_h=df["charging_h"].mask(bad_ch))
    log["rows_out"] = len(df)
    return df.reset_index(drop=True), log


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Local-time features (behaviour depends on local clock), computed per time zone."""
    out = []
    for tz, part in df.groupby("tz", sort=False):
        a = part["arrival_utc"].dt.tz_convert(tz)
        d = part["departure_utc"].dt.tz_convert(tz)
        part = part.assign(
            arrival_hour_local=a.dt.hour + a.dt.minute / 60,
            departure_hour_local=d.dt.hour + d.dt.minute / 60,
            arrival_date_local=a.dt.strftime("%Y-%m-%d"),
            weekday=a.dt.dayofweek,
            is_weekend=a.dt.dayofweek >= 5,
        )
        out.append(part)
    return pd.concat(out).sort_values(["source", "arrival_utc"]).reset_index(drop=True)


def assign_split(df: pd.DataFrame, cuts: dict[str, dict[str, str]]) -> pd.DataFrame:
    """Time-based split per source (golden rule 3). Rows outside the window -> 'excluded'.

    cuts[source] = {"start": ..., "val": ..., "test": ..., "end": ...} (UTC dates, end exclusive).
    """
    split = pd.Series("excluded", index=df.index, dtype="string")
    for src, c in cuts.items():
        t = df["arrival_utc"]
        m = df["source"] == src
        start, val, test, end = (pd.Timestamp(c[k], tz="UTC") for k in ("start", "val", "test", "end"))
        split[m & (t >= start) & (t < val)] = "train"
        split[m & (t >= val) & (t < test)] = "val"
        split[m & (t >= test) & (t < end)] = "test"
    return df.assign(split=split)
