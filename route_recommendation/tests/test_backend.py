"""C3 routing / stop-planning tests (needs seeded road graph + c3.db; trip logs deleted afterwards)."""

import numpy as np
import pandas as pd
import pytest

from route_recommendation.charging_stops import selector


def test_multi_stop_plan_reaches_destination():
    n = 100  # 100 segments x 0.5 kWh = 50 kWh trip, 20 kWh battery -> needs several stops
    km = np.arange(1, n + 1) * 2.0
    lat, lon = np.full(n, 7.0), 80.0 + np.arange(n) * 0.018
    ch = pd.DataFrame({"osm_id": [f"n{i}" for i in range(0, n, 10)], "name": None, "operator": None,
                       "lat": 7.0, "lon": lon[::10], "max_kw": 50.0, "sockets": "type2_combo"})
    veh = {"connector": "ccs;type2", "max_dc_kw": 50, "max_ac_kw": 7.4}
    p = selector.plan_stops(lat, lon, km, np.full(n, 0.5), 95, 20, 15, ch, veh)
    assert p["feasible"] and len(p["stops"]) >= 2
    assert p["soc_profile"].min() >= 15 - 1e-6 and p["arrival_soc"] >= 15


def test_incompatible_connector_is_ignored():
    assert selector.compatible("chademo;type1", "type2_combo") == "no"
    assert selector.compatible("ccs;type2", "type2_combo;type2") == "yes"
    assert selector.compatible("ccs;type2", None) == "unknown"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from route_recommendation.backend.app import main
    from route_recommendation.backend.app.core import SessionLocal, TripLog
    with TestClient(main.app) as c:
        yield c
    db = SessionLocal(); db.query(TripLog).filter(TripLog.origin == "pytest").delete(); db.commit(); db.close()


def test_plan_colombo_kandy(client):
    r = client.post("/c3/plan", json={"origin": {"lat": 6.9344, "lon": 79.8428, "name": "pytest"},
                                      "destination": {"lat": 7.2906, "lon": 80.6337, "name": "Kandy"},
                                      "vehicle_id": 0, "start_soc_pct": 95}).json()
    assert 100 < r["routes"][0]["distance_km"] < 140  # real road distance ~115-120 km
    assert sum(1 for x in r["routes"] if x.get("recommended")) == 1
    assert {"physics", "hybrid", "constant"} <= set(r["routes"][0]["energy_kwh"])
