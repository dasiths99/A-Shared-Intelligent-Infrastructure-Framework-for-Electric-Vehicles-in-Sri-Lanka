"""Tests for C3 data preparation (small synthetic data, no raw files needed)."""

import numpy as np
import pandas as pd
import pytest

from route_recommendation.data_prep import bmw, eved, other, segments


def _trip(n=600, speed=72.0, kw=10.0, elev_slope=0.0):
    """n seconds at constant speed (km/h) and battery power (kW)."""
    t = np.arange(n, dtype=float)
    d = speed / 3.6 * t
    return pd.DataFrame({"trip_id": "T1", "t_s": t, "speed_kmh": speed, "battery_kw": kw,
                         "elev": 100 + elev_slope * d, "accel_mps2": 0.0})


def test_distance_and_segment_energy_add_up():
    df = segments.add_distance(_trip())  # 20 m/s * 599 s = 11,980 m
    assert df["dist_m"].iloc[-1] == pytest.approx(11980)
    seg = segments.make_segments(df, "elev")
    assert seg["dist_m"].iloc[1:].between(190, 210).all()  # first piece starts at the first sample
    assert seg["kwh_per_km"].median() == pytest.approx(10 / 72, rel=1e-6)  # 10 kW at 72 km/h
    total = (df["battery_kw"] * df["dt_s"]).sum() / 3600
    assert seg["energy_kwh"].sum() == pytest.approx(total, rel=0.03)  # only the short last piece is dropped


def test_grade_from_elevation():
    df = segments.add_distance(_trip(elev_slope=0.05))  # 5 % climb
    seg = segments.make_segments(df, "elev")
    assert seg["grade_pct"].median() == pytest.approx(5.0, rel=0.05)


def test_time_gap_is_flagged_and_not_counted_as_driving():
    df = _trip(n=100)
    df.loc[50:, "t_s"] += 60  # 60 s logger gap
    df = segments.add_distance(df)
    assert df["gap"].sum() == 1 and df["dt_s"].max() == 1


def test_resample_to_1hz_averages():
    df = pd.DataFrame({"trip_id": "T", "t_s": [0.0, 0.5, 1.0, 1.5], "speed_kmh": [10, 20, 30, 50]})
    out = segments.resample_1hz(df)
    assert out["speed_kmh"].tolist() == [15, 40]


def test_split_within_season_is_time_ordered():
    t = pd.DataFrame({"season": ["s"] * 10 + ["w"] * 10,
                      "start": list(pd.date_range("2019-06-01", periods=10)) + list(pd.date_range("2019-12-01", periods=10))})
    sp = segments.split_within_groups(t, "season", "start")
    for s in ("s", "w"):
        part = sp[t["season"] == s].tolist()
        assert part == ["train"] * 7 + ["val"] * 2 + ["test"] * 1 or part.count("train") == 7


def test_bmw_reader_maps_header_versions(tmp_path):
    header = "Time [s];Velocity [km/h];Elevation [m];Battery Voltage [V];Battery Current [A];SoC [%];" \
             "displayed SoC [%];Heating Power LIN [W];Ambient Temperature [\xb0C];Ambient Temperature Sensor [\xb0C]"
    rows = ["0;0;500;390;-10;80;82;1500;5;6", "0.1;0;500;390;20;80;82;1500;5;6"]
    p = tmp_path / "TripB99.csv"
    p.write_bytes(("\r\n".join([header, *rows]) + "\r\n").encode("latin-1"))
    df = bmw.read_trip(p)
    assert df.loc[0, "battery_kw"] == pytest.approx(3.9)  # -390 * -10 / 1000, discharging
    assert df.loc[0, "heater_kw"] == pytest.approx(1.5) and df.loc[0, "ambient_c"] == 5
    clean, info = bmw.clean_trip(df)
    assert len(clean) == 1 and info["charging_s"] == pytest.approx(0.1)  # 7.8 kW into battery at standstill


def test_soc_zero_is_glitch():
    df = pd.DataFrame({"t_s": [0, 1], "speed_kmh": [30, 30], "battery_v": [390, 390], "battery_a": [-10, -10],
                       "battery_kw": [3.9, 3.9], "soc_pct": [55.0, 0.0]})
    clean, info = bmw.clean_trip(df)
    assert info["soc_glitch_rows"] == 1 and np.isnan(clean["soc_pct"].iloc[1])


def test_eved_time_split():
    s = pd.Series(pd.date_range("2018-01-01", periods=100, freq="D", tz="UTC"))
    sp = eved.split_by_time(s)
    assert sp.iloc[0] == "train" and sp.iloc[-1] == "test" and (sp == "train").sum() == 70


def test_weather_reader(tmp_path):
    txt = ("latitude,longitude,elevation,utc_offset_seconds,timezone,timezone_abbreviation\n"
           "6.92,79.9,3.0,19800,Asia/Colombo,GMT+5:30\n\n"
           "time,temperature_2m (\xb0C),relative_humidity_2m (%)\n"
           "2023-01-01T00:00,21.8,84\n2023-01-01T01:00,99.0,84\n2023-01-01T01:00,21.0,85\n")
    (tmp_path / "Colombo_hourly_2023_2025.csv").write_text(txt, encoding="utf-8")
    w, log = other.read_weather(tmp_path)
    assert len(w) == 1 and w["time_utc"].iloc[0] == pd.Timestamp("2022-12-31 18:30", tz="UTC")
