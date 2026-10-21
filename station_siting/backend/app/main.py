"""C2 backend - run from the project root (seed the database first, see README):

    python -m uvicorn station_siting.backend.app.main:app --port 8002 --reload

API docs: http://localhost:8002/docs
"""

from __future__ import annotations

import io
import json
from typing import Literal

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from station_siting.mcdm.ahp import CRIT, DEFAULT_JUDGEMENTS, ahp

from . import services
from .config import CORS_ORIGINS, DEFAULTS
from .db import Base, OptimizationRun, engine, get_db

Base.metadata.create_all(engine)
app = FastAPI(title="J26-IT-430 · C2 Station Siting API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
MODES = ["temporal", "static", *services.PERIODS]
# Literal (not Query(enum=...)) - newer FastAPI versions reject the 'enum' keyword
Mode = Literal["temporal", "static", "weekday_peak", "weekday_offpeak", "weekend_peak", "weekend_offpeak"]
assert list(Mode.__args__) == MODES, "keep Mode in sync with services.PERIODS"


def _features(df: pd.DataFrame, props: list[str]) -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
         "properties": {k: (None if pd.isna(r[k]) else r[k]) for k in props}} for _, r in df.iterrows()]}


@app.get("/c2/health")
def health():
    return {"status": "ok", "component": "C2 station siting"}


@app.get("/c2/meta")
def meta():
    m = services.meta()
    return {"criteria": CRIT, "default_judgements": DEFAULT_JUDGEMENTS, "defaults": DEFAULTS, "modes": MODES,
            "district": json.loads(m["district_geojson"]), "period_weights": json.loads(m["period_weights"]),
            "seeded_utc": m.get("seeded_utc"), "counts": {"hexagons": len(services.hexes()),
            "candidates": len(services.candidates()), "substations": len(services.substations()),
            "chargers": len(services.chargers())}}


@app.get("/c2/hexagons")
def hexagons(mode: Mode = Query("temporal")):
    h = services.hexes()
    col = "D_static" if mode == "static" else f"D_{mode}"
    mx = float(h[col].max())
    return {"type": "FeatureCollection", "mode": mode, "max": mx, "features": [
        {"type": "Feature", "geometry": json.loads(g), "properties": {"h3": k, "demand": round(float(v) / mx, 4),
         "population": round(float(p)), "traffic": round(float(t), 2)}}
        for k, g, v, p, t in zip(h.h3, h.geojson, h[col], h.population, h.traffic_proxy)]}


@app.get("/c2/substations")
def substations():
    s = services.substations()
    return _features(s, ["ceb_name", "capacity_2025_mva", "peak_2025_mva", "spare_2025_mva", "utilisation_2025",
                         "location_source", "serves_study_area"])


@app.get("/c2/chargers")
def chargers():
    return _features(services.chargers(), ["name", "operator", "sockets", "max_kw", "in_district"])


class AhpIn(BaseModel):
    judgements: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_JUDGEMENTS))


@app.post("/c2/ahp")
def ahp_weights(body: AhpIn):
    try:
        return ahp(body.judgements)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"bad judgements: {e}")


class OptimizeIn(BaseModel):
    label: str = "run"
    n_sites: int = Field(DEFAULTS["n_sites"], ge=1, le=60)
    radius_m: int = Field(DEFAULTS["radius_m"], ge=500, le=25000)
    station_mw: float = Field(DEFAULTS["station_mw"], gt=0, le=10)
    ev_share: float = Field(DEFAULTS["ev_share"], gt=0, le=1)
    power_factor: float = Field(DEFAULTS["power_factor"], gt=0.5, le=1)
    demand_mode: str = DEFAULTS["demand_mode"]
    grid_constraint: bool = DEFAULTS["grid_constraint"]
    judgements: dict[str, float] | None = None


@app.post("/c2/optimize")
def optimize(body: OptimizeIn, db: Session = Depends(get_db)):
    if body.demand_mode not in MODES:
        raise HTTPException(400, f"demand_mode must be one of {MODES}")
    a = ahp(body.judgements or DEFAULT_JUDGEMENTS)
    p = body.model_dump() | {"weights": a["weights"]}
    out = services.run(p)
    out["ahp"] = {"weights": a["weights"], "CR": a["CR"], "consistent": a["consistent"]}
    run = OptimizationRun(label=body.label, params_json=json.dumps(p), metrics_json=json.dumps({k: out[k] for k in ("metrics", "baselines", "ahp")}),
                          sites_json=json.dumps(out["sites"]), n_sites=len(out["sites"]),
                          coverage_pct=out["metrics"].get("coverage_temporal_pct", 0.0))
    db.add(run); db.commit(); db.refresh(run)
    return {"run_id": run.id, **out}


@app.get("/c2/runs")
def runs(db: Session = Depends(get_db)):
    return [{"id": r.id, "label": r.label, "created_utc": r.created_utc, "n_sites": r.n_sites,
             "coverage_pct": round(r.coverage_pct, 1), "params": json.loads(r.params_json)}
            for r in db.query(OptimizationRun).order_by(OptimizationRun.id.desc()).limit(30)]


@app.get("/c2/runs/{run_id}/export")
def export(run_id: int, fmt: Literal["geojson", "csv"] = Query("geojson"), db: Session = Depends(get_db)):
    r = db.get(OptimizationRun, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    sites = pd.DataFrame(json.loads(r.sites_json))
    if fmt == "csv":
        buf = io.StringIO(); sites.to_csv(buf, index=False)
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=c2_run_{run_id}.csv"})
    fc = _features(sites, [c for c in sites.columns if c not in ("lat", "lon")])
    return Response(json.dumps(fc), media_type="application/geo+json",
                    headers={"Content-Disposition": f"attachment; filename=c2_run_{run_id}.geojson"})
