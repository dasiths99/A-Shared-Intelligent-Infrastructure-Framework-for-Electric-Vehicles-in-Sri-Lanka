"""C3 backend - run from the project root (seed first, see README):

    python -m uvicorn route_recommendation.backend.app.main:app --port 8003 --reload

API docs: http://localhost:8003/docs
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from route_recommendation.charging_stops import selector
from route_recommendation.energy import route_energy

from . import core
from .core import CORS_ORIGINS, Base, TripLog, engine, get_db

Base.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(_app):
    core.graph()  # load the road graph once at startup (~3 s)
    yield


app = FastAPI(title="J26-IT-430 · C3 Route & Charging-Stop API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
PHYS_KEYS = ["mass_kg", "crr", "cda_m2", "eta_drive", "eta_regen", "aux_base_kw", "aux_cold_kw_per_C", "aux_hot_kw_per_C"]


@app.get("/c3/health")
def health():
    return {"status": "ok", "component": "C3 route & charging stop"}


@app.get("/c3/vehicles")
def vehicles():
    v = core.vehicles()
    return json.loads(v.to_json(orient="records"))


class VehicleIn(BaseModel):
    name: str
    usable_kwh: float = Field(gt=5, lt=250)
    max_dc_kw: float | None = None
    max_ac_kw: float | None = 7.4
    connector: str = "ccs;type2"
    mass_kg: float = Field(gt=600, lt=4000)
    cda_m2: float = Field(gt=0.3, lt=1.5)
    crr: float = Field(0.010, gt=0.004, lt=0.03)
    eta_drive: float = Field(0.90, gt=0.6, lt=0.99)
    eta_regen: float = Field(0.65, gt=0.2, lt=0.95)
    aux_base_kw: float = 0.5
    aux_cold_kw_per_C: float = 0.1
    aux_hot_kw_per_C: float = 0.08
    params_source: str = Field(min_length=3, description="spec sheet / brochure used")


@app.post("/c3/vehicles")
def add_vehicle(body: VehicleIn):
    """Add a Sri Lankan model (e.g. BYD Atto 3) with spec-sheet physics values - physics model only (no hybrid)."""
    v = core.vehicles()
    row = body.model_dump() | {"id": int(v["id"].max()) + 1, "hybrid_model": None}
    pd.DataFrame([row]).to_sql("vehicles", engine, if_exists="append", index=False)
    core.vehicles_reload()
    return row


@app.get("/c3/places")
def places():
    return json.loads(core.places().to_json(orient="records"))


@app.get("/c3/chargers")
def chargers():
    rows = json.loads(core.chargers().to_json(orient="records"))  # NaN -> null
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
         "properties": {k: r[k] for k in ("osm_id", "name", "operator", "max_kw", "sockets")}} for r in rows]}


class Point(BaseModel):
    lat: float
    lon: float
    name: str | None = None


class PlanIn(BaseModel):
    origin: Point
    destination: Point
    vehicle_id: int
    start_soc_pct: float = Field(90, ge=10, le=100)
    reserve_pct: float = Field(15, ge=5, le=40)


def _ambient(lat: float, lon: float) -> tuple[float, str]:
    w = core.weather_means()
    i = int(np.argmin((w.lat - lat) ** 2 + (w.lon - lon) ** 2))
    return float(w.temp_c.iloc[i]), str(w.town.iloc[i])


def _route_detail(g, path, veh: dict, p: dict, start_soc: float, reserve: float, ambient: float, model) -> dict:
    e = path.edges
    s = route_energy.segments(g.length[e], g.speed[e], g.elev[g.u[e]], g.elev[g.v[e]], ambient)
    est = route_energy.estimate(s, p, model, veh.get("const_kwh_km"))
    best = np.asarray(est.get("hybrid", est["physics"]))
    km = s.km_end.to_numpy()
    # coordinates at segment ends for the map / charger search
    cum = np.cumsum(g.length[e]) / 1000
    idx = np.minimum(np.searchsorted(cum, km), len(e) - 1)
    lat, lon = g.lat[g.v[e][idx]], g.lon[g.v[e][idx]]
    plan = selector.plan_stops(lat, lon, km, best, start_soc, veh["usable_kwh"], reserve, core.chargers(), veh)
    soc = plan.pop("soc_profile")
    stop = plan
    drive_min = float(s.duration_s.sum() / 60)
    charge_min, arrival = float(plan["charge_min"]), float(plan["arrival_soc"])
    step = max(1, len(s) // 300)
    return {
        "distance_km": round(float(km[-1]), 1), "drive_min": round(drive_min), "charge_min": round(charge_min),
        "total_min": round(drive_min + charge_min),
        "energy_kwh": {k: round(float(v.sum()), 2) for k, v in est.items()},
        "climb_m": round(float(s.elev_change_m.clip(lower=0).sum())), "max_elev_m": round(float(s.elev_end_m.max())),
        "arrival_soc_pct": round(arrival, 1), "feasible": bool(plan["feasible"]), "n_stops": len(plan["stops"]),
        "stop": stop,
        "geometry": [[round(float(a), 5), round(float(b), 5)] for a, b in zip(g.lat[g.u[e]][::max(1, len(e) // 1500)], g.lon[g.u[e]][::max(1, len(e) // 1500)])]
                    + [[round(float(g.lat[g.v[e][-1]]), 5), round(float(g.lon[g.v[e][-1]]), 5)]],
        "profile": [{"km": round(float(k), 2), "elev": round(float(z)), "soc": round(float(c), 1),
                     "soc_constant": round(float(start_soc - 100 * np.cumsum(est["constant"])[i] / veh["usable_kwh"]), 1) if "constant" in est else None}
                    for i, (k, z, c) in enumerate(zip(km, s.elev_end_m, soc)) if i % step == 0 or i == len(s) - 1],
    }


@app.post("/c3/plan")
def plan(body: PlanIn, db: Session = Depends(get_db)):
    g = core.graph()
    vt = core.vehicles()
    if body.vehicle_id not in set(vt.id):
        raise HTTPException(404, "vehicle not found")
    veh = vt[vt.id == body.vehicle_id].iloc[0].to_dict()
    p = {k: float(veh[k]) for k in PHYS_KEYS}
    key = {"BMW i3 (60 Ah)": "BMW i3|18.8", "Nissan Leaf 2013 (24 kWh)": "Nissan Leaf|24.0"}.get(veh["name"])
    veh["const_kwh_km"] = core.const_kwh_per_km().get(key) if key else None
    model = core.hybrid(veh.get("hybrid_model"))
    src, ds = g.snap(body.origin.lat, body.origin.lon)
    dst, dd = g.snap(body.destination.lat, body.destination.lon)
    if src == dst:
        raise HTTPException(400, "origin and destination are the same place")
    ambient, town = _ambient((body.origin.lat + body.destination.lat) / 2, (body.origin.lon + body.destination.lon) / 2)
    variants = {"Shortest": g.length, "Fastest": g.time_s(), "Energy-aware": g.energy_kwh(p, ambient)}
    routes, seen = [], {}
    for name, w in variants.items():
        path = g.shortest(src, dst, w)
        if path is None:
            raise HTTPException(400, "no road connection found")
        sig = (len(path.nodes), int(path.nodes[len(path.nodes) // 2]))
        if sig in seen:
            seen[sig]["labels"].append(name)
            continue
        r = _route_detail(g, path, veh, p, body.start_soc_pct, body.reserve_pct, ambient, model)
        r["labels"] = [name]
        seen[sig] = r
        routes.append(r)
    # ranking: lower energy (0.5), lower total time (0.3), higher arrival SoC (0.2)
    E = np.array([r["energy_kwh"].get("hybrid", r["energy_kwh"]["physics"]) for r in routes])
    T = np.array([r["total_min"] for r in routes]); A = np.array([r["arrival_soc_pct"] for r in routes])
    nz = lambda x: (x - x.min()) / (x.max() - x.min()) if x.max() > x.min() else x * 0
    infeasible = np.array([0.0 if r["feasible"] else 10.0 for r in routes])  # never recommend a route that strands the car
    score = 0.5 * nz(E) + 0.3 * nz(T) - 0.2 * nz(A) + infeasible
    for r, s_ in zip(routes, score):
        r["score"] = round(float(s_), 3)
    routes.sort(key=lambda r: r["score"])
    routes[0]["recommended"] = True
    out = {"vehicle": veh["name"], "usable_kwh": veh["usable_kwh"], "ambient_c": round(ambient, 1), "weather_town": town,
           "snap_m": {"origin": round(ds), "destination": round(dd)}, "energy_model": "hybrid" if model else "physics",
           "routes": routes,
           "notes": ["Road speeds = OSM limit or typical value per road class (no Sri Lankan traffic data).",
                     "Charger power unknown in OSM -> 22 kW assumed; busyness = placeholder until C1 merge.",
                     "Hybrid model trained on flat data (Munich / Michigan) - hill accuracy needs Sri Lankan pilot trips."]}
    db.add(TripLog(origin=body.origin.name or f"{body.origin.lat:.3f},{body.origin.lon:.3f}",
                   destination=body.destination.name or f"{body.destination.lat:.3f},{body.destination.lon:.3f}",
                   vehicle_id=body.vehicle_id, start_soc_pct=body.start_soc_pct,
                   result_json=json.dumps({"routes": [{k: r[k] for k in ("labels", "distance_km", "total_min", "energy_kwh", "arrival_soc_pct")} for r in routes]})))
    db.commit()
    return out
