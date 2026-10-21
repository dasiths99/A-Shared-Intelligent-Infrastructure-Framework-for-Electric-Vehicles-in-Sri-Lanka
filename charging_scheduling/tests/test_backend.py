"""C1 API tests on a temporary database (login data and sessions stay separate)."""

import importlib
import sqlite3
import sys

import pytest


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("c1") / "test.db"
    import os
    os.environ["C1_DATABASE_URL"] = f"sqlite:///{db.as_posix()}"
    for m in [m for m in sys.modules if m.startswith("charging_scheduling.backend")]:
        del sys.modules[m]
    main = importlib.import_module("charging_scheduling.backend.app.main")
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c, db


def _login(c):
    r = c.post("/c1/auth/register", json={"email": "a@b.lk", "password": "secret1", "district": "Colombo", "consent": True})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_register_requires_consent(client):
    c, _ = client
    r = c.post("/c1/auth/register", json={"email": "x@y.lk", "password": "secret1", "district": "Colombo", "consent": False})
    assert r.status_code == 400


def test_plan_charges_off_peak_and_saves_money(client):
    c, db = client
    h = _login(c)
    leaf = next(m for m in c.get("/c1/vehicle-models").json() if m["model"] == "Leaf")
    v = c.post("/c1/vehicles", json={"model_id": leaf["id"]}, headers=h).json()
    p = c.post("/c1/plan", json={"vehicle_id": v["id"], "soc_now_pct": 30, "soc_target_pct": 80,
                                 "plug_in_local": "19:00", "departure_local": "07:00"}, headers=h).json()
    assert p["ready"] and p["saving_lkr"] > 0
    assert all(w["start"] >= "22:30" or w["start"] < "05:30" for w in p["windows"])  # off-peak only
    # privacy: charging_sessions has no user id / email column
    cols = [r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(charging_sessions)")]
    assert "user_id" not in cols and "email" not in cols and "vehicle_random_id" in cols


def test_delete_me_removes_everything(client):
    c, db = client
    h = {"Authorization": "Bearer " + c.post("/c1/auth/login", json={"email": "a@b.lk", "password": "secret1"}).json()["token"]}
    assert c.delete("/c1/auth/me", headers=h).json()["deleted"]
    con = sqlite3.connect(db)
    assert con.execute("select count(*) from users").fetchone()[0] == 0
    assert con.execute("select count(*) from charging_sessions").fetchone()[0] == 0
