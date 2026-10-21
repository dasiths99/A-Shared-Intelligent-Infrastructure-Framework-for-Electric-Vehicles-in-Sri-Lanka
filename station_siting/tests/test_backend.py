"""C2 API tests (needs the seeded c2.db; runs are deleted afterwards)."""

import pytest

from station_siting.mcdm.ahp import DEFAULT_JUDGEMENTS, ahp


def test_ahp_default_is_consistent():
    a = ahp(DEFAULT_JUDGEMENTS)
    assert a["consistent"] and abs(sum(a["weights"].values()) - 1) < 1e-9


def test_ahp_detects_inconsistent_judgements():
    bad = dict(DEFAULT_JUDGEMENTS) | {"demand|grid": 1 / 7, "grid|road": 7, "demand|road": 7}
    assert not ahp(bad)["consistent"]


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from station_siting.backend.app import main
    from station_siting.backend.app.db import OptimizationRun, SessionLocal
    with TestClient(main.app) as c:
        yield c
    db = SessionLocal(); db.query(OptimizationRun).filter(OptimizationRun.label == "pytest").delete(); db.commit(); db.close()


def test_grid_constraint_never_overloads(client):
    r = client.post("/c2/optimize", json={"label": "pytest", "n_sites": 10, "station_mw": 2.0}).json()
    assert r["metrics"]["grid_violations"] == 0
    assert r["metrics"]["coverage_temporal_pct"] > r["baselines"]["Traffic-only top-N"]["coverage_temporal_pct"]
    assert len(r["sites"]) <= 10
