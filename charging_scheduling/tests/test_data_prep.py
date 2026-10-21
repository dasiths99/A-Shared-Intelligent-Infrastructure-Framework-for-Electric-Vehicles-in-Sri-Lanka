"""Tests for C1 data preparation (small synthetic data, no raw files needed)."""

import json

import pandas as pd
import pytest

from charging_scheduling.data_prep import recon, sessions


def _sess(**over):
    base = dict(source="x", site="s", session_id="1", user_id="u", station_id="st",
                arrival_utc=pd.Timestamp("2019-01-01 08:00", tz="UTC"),
                departure_utc=pd.Timestamp("2019-01-01 12:00", tz="UTC"),
                done_charging_utc=pd.NaT, kwh=10.0, charging_h=2.0, tz="UTC")
    base.update(over)
    return base


def test_rules_drop_bad_sessions():
    t = pd.Timestamp("2019-01-01 08:00", tz="UTC")
    df = pd.DataFrame([
        _sess(session_id="ok"),
        _sess(session_id="short", departure_utc=t + pd.Timedelta(minutes=2)),
        _sess(session_id="long", departure_utc=t + pd.Timedelta(hours=60)),
        _sess(session_id="zero", kwh=0.0),
        _sess(session_id="huge", kwh=150.0),
        _sess(session_id="fast", kwh=90.0, departure_utc=t + pd.Timedelta(hours=1)),
        _sess(session_id="notime", arrival_utc=pd.NaT),
        _sess(session_id="ok", station_id="dup"),  # duplicate session id
    ])
    df["station_id"] = df["station_id"] + df["session_id"]  # keep rows distinct for the station/time rule
    out, log = sessions.apply_rules(df)
    assert out["session_id"].tolist() == ["ok"]
    assert log["stay_too_short"] == 1 and log["stay_too_long"] == 1
    assert log["zero_or_missing_kwh"] == 1 and log["kwh_too_large"] == 1
    assert log["impossible_avg_power"] == 1 and log["duplicate_session_id"] == 1
    assert out.loc[0, "stay_h"] == pytest.approx(4.0)


def test_same_station_same_time_is_duplicate():
    df = pd.DataFrame([_sess(session_id="a"), _sess(session_id="b")])
    out, log = sessions.apply_rules(df)
    assert len(out) == 1 and log["duplicate_station_time"] == 1


def test_same_session_with_seconds_and_without_is_duplicate():
    t = pd.Timestamp("2023-07-01 10:05", tz="UTC")
    df = pd.DataFrame([_sess(session_id="a", arrival_utc=t),
                       _sess(session_id="b", arrival_utc=t + pd.Timedelta(seconds=41),
                             departure_utc=pd.Timestamp("2023-07-01 12:00:12", tz="UTC"))])
    df["departure_utc"] = df["departure_utc"].where(df["session_id"] == "b", pd.Timestamp("2023-07-01 12:00", tz="UTC"))
    out, log = sessions.apply_rules(df)
    assert len(out) == 1 and log["duplicate_station_minute_kwh"] == 1


def test_charging_time_longer_than_stay_is_set_missing():
    out, log = sessions.apply_rules(pd.DataFrame([_sess(charging_h=9.0)]))
    assert pd.isna(out.loc[0, "charging_h"]) and log["charging_h_set_missing"] == 1


def test_time_features_use_local_clock():
    df = pd.DataFrame([_sess(tz="America/Los_Angeles")])  # 08:00 UTC = 00:00 PST
    df["stay_h"] = 4.0
    out = sessions.add_time_features(df)
    assert out.loc[0, "arrival_hour_local"] == 0.0
    assert out.loc[0, "weekday"] == 1  # Tuesday 1 Jan 2019


def test_split_is_time_based():
    t = pd.to_datetime(["2019-01-05", "2019-06-05", "2019-09-05", "2021-01-01"], utc=True)
    df = pd.DataFrame({"source": "acn", "arrival_utc": t})
    out = sessions.assign_split(df, {"acn": {"start": "2019-01-01", "val": "2019-06-01",
                                             "test": "2019-09-01", "end": "2020-01-01"}})
    assert out["split"].tolist() == ["train", "val", "test", "excluded"]


def test_acn_loader_parses_gmt_and_first_user_input(tmp_path):
    s = {"sessionID": "a", "userID": "000000007", "stationID": "1-1", "connectionTime": "Wed, 05 Sep 2018 11:08:09 GMT",
         "disconnectTime": "Wed, 05 Sep 2018 14:09:02 GMT", "doneChargingTime": "Wed, 05 Sep 2018 13:08:09 GMT",
         "kWhDelivered": 7.1, "timezone": "America/Los_Angeles",
         "userInputs": [{"kWhRequested": 8.0, "requestedDeparture": "Wed, 05 Sep 2018 15:45:09 GMT",
                         "minutesAvailable": 277, "milesRequested": 20, "WhPerMile": 400,
                         "modifiedAt": "Wed, 05 Sep 2018 11:08:31 GMT"},
                        {"kWhRequested": 12.0}]}
    (tmp_path / "acn_jpl_sessions.json").write_text(json.dumps([s]))
    df = sessions.load_acn(tmp_path)
    r = df.iloc[0]
    assert r["arrival_utc"] == pd.Timestamp("2018-09-05 11:08:09", tz="UTC")
    assert r["charging_h"] == pytest.approx(2.0)
    assert r["kwh_requested"] == 8.0 and r["n_user_inputs"] == 2
    assert r["user_id"] == "acn_000000007" and r["site"] == "jpl"


def test_recon_cumulative_to_intervals():
    t = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:15", "2024-01-01 00:30",
                        "2024-01-01 01:30", "2024-01-01 01:45", "2024-01-01 02:00"])
    r = pd.DataFrame({"hh": 1, "t_local": t,
                      "imp": [100.0, 100.5, 101.0, 102.0, 101.0, 110.0],  # gap, reset, spike
                      "exp": 0.0})
    out, log = recon.readings_to_intervals(r)
    assert out["import_kwh"].tolist() == pytest.approx([0.5, 0.5])
    # first kept interval: reading 00:15 local covers 00:00-00:15 local = 18:30 UTC previous day
    assert out["interval_start_utc"].iloc[0] == pd.Timestamp("2023-12-31 18:30", tz="UTC")
    assert log["gap_not_15min"] == 1 and log["negative_diff_meter_reset"] == 1 and log["too_large_gt_15kW"] == 1


def test_baseload_needs_enough_households():
    t = pd.Timestamp("2024-01-01 00:00", tz="UTC")
    iv = pd.DataFrame({"household_id": range(60), "interval_start_utc": t, "import_kwh": 0.25})
    iv = pd.concat([iv, pd.DataFrame({"household_id": [1], "interval_start_utc": [t + recon.SLOT],
                                      "import_kwh": [1.0]})])
    b = recon.build_baseload(iv, min_households=50)
    assert len(b) == 1 and b.loc[0, "mean_kw"] == pytest.approx(1.0)
    assert b.loc[0, "slot_of_day"] == 22  # 00:00 UTC = 05:30 Colombo -> slot 22
