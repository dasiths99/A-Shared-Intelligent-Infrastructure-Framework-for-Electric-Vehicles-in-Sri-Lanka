"""C1 API routes (prefix /c1)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from charging_scheduling.scheduler import lp
from charging_scheduling.simulator import scenario
from charging_scheduling.forecasting import baseload
from shared import config as shared_config

from . import services
from .config import DISTRICTS, N_HOMES_FEEDER, TZ
from .db import get_db
from .models import ChargingSession, User, Vehicle, VehicleModel
from .schemas import (LoginIn, PlanIn, RegisterIn, SessionOut, TokenOut, VehicleIn, VehicleModelIn, VehicleModelOut,
                      VehicleOut)
from .security import current_user, hash_password, new_token, verify_password

router = APIRouter(prefix="/c1")
CHARGE_EFF = 0.90  # AC charging efficiency (grid -> battery), assumption
COLD_START_SESSIONS = 10


# ------------------------------------------------------------------ info
@router.get("/health")
def health():
    return {"status": "ok", "component": "C1 charging scheduling"}


@router.get("/meta")
def meta():
    t = shared_config.TOU_DOMESTIC
    return {"districts": DISTRICTS, "tariff": t, "fixed_lkr_month": shared_config.TOU_FIXED_LKR_PER_MONTH,
            "slot_minutes": shared_config.SLOT_MINUTES}


# ------------------------------------------------------------------ auth (users table only)
@router.post("/auth/register", response_model=TokenOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if body.district not in DISTRICTS:
        raise HTTPException(400, "unknown district")
    if not body.consent:
        raise HTTPException(400, "consent is required to use the app")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(409, "email already registered")
    u = User(email=body.email, password_hash=hash_password(body.password), district=body.district,
             consent=True, token=new_token())
    db.add(u); db.commit()
    return TokenOut(token=u.token, district=u.district)


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "wrong email or password")
    u.token = new_token(); db.commit()
    return TokenOut(token=u.token, district=u.district)


@router.delete("/auth/me")
def delete_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Right to delete (PDPA): removes login data, vehicles and their sessions."""
    for v in db.query(Vehicle).filter(Vehicle.user_id == user.id).all():
        db.query(ChargingSession).filter(ChargingSession.vehicle_random_id == v.random_id).delete()
        db.delete(v)
    db.delete(user); db.commit()
    return {"deleted": True}


# ------------------------------------------------------------------ vehicles
@router.get("/vehicle-models", response_model=list[VehicleModelOut])
def vehicle_models(db: Session = Depends(get_db)):
    return db.query(VehicleModel).order_by(VehicleModel.make, VehicleModel.model, VehicleModel.usable_kwh).all()


@router.post("/vehicle-models", response_model=VehicleModelOut)
def add_vehicle_model(body: VehicleModelIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Add a model from a brochure / spec sheet (e.g. BYD Atto 3) - `source` is required."""
    m = VehicleModel(**body.model_dump()); db.add(m); db.commit(); db.refresh(m)
    return m


def _vehicle_out(v: Vehicle, db: Session) -> VehicleOut:
    out = VehicleOut.model_validate(v)
    out.model = VehicleModelOut.model_validate(db.get(VehicleModel, v.model_id))
    return out


@router.get("/vehicles", response_model=list[VehicleOut])
def my_vehicles(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [_vehicle_out(v, db) for v in db.query(Vehicle).filter(Vehicle.user_id == user.id).all()]


@router.post("/vehicles", response_model=VehicleOut)
def add_vehicle(body: VehicleIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not db.get(VehicleModel, body.model_id):
        raise HTTPException(404, "vehicle model not found")
    v = Vehicle(user_id=user.id, **body.model_dump()); db.add(v); db.commit(); db.refresh(v)
    return _vehicle_out(v, db)


# ------------------------------------------------------------------ planning
def _local_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz=TZ)


def _at(day: pd.Timestamp, hhmm: str) -> pd.Timestamp:
    h, m = map(int, hhmm.split(":"))
    return day.normalize() + pd.Timedelta(hours=h, minutes=m)


@router.post("/plan")
def make_plan(body: PlanIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    v = db.query(Vehicle).filter(Vehicle.id == body.vehicle_id, Vehicle.user_id == user.id).first()
    if not v:
        raise HTTPException(404, "vehicle not found")
    if body.soc_target_pct <= body.soc_now_pct:
        raise HTTPException(400, "target SoC must be higher than current SoC")
    model = db.get(VehicleModel, v.model_id)
    now = _local_now()
    plug = _at(now, body.plug_in_local) if body.plug_in_local else now
    plug = plug.floor("15min")

    # departure: personal history (>= 10 sessions) else profile default (cold start)
    hist = db.query(ChargingSession).filter(ChargingSession.vehicle_random_id == v.random_id).all()
    if body.departure_local:
        dep_hhmm, dep_source = body.departure_local, "entered by driver"
    elif len(hist) >= COLD_START_SESSIONS:
        mins = [(pd.Timestamp(s.departure_utc).tz_convert(TZ).hour * 60 + pd.Timestamp(s.departure_utc).tz_convert(TZ).minute) for s in hist]
        med = int(np.median(mins))
        dep_hhmm, dep_source = f"{med // 60:02d}:{med % 60:02d}", f"learned from your last {len(hist)} sessions"
    else:
        dep_hhmm, dep_source = v.usual_departure, f"profile default (cold start: {len(hist)}/{COLD_START_SESSIONS} sessions)"
    dep = _at(plug, dep_hhmm)
    if dep <= plug:
        dep += pd.Timedelta(days=1)
    dep = dep.floor("15min")

    usable = model.usable_kwh * v.battery_health_pct / 100
    need = (body.soc_target_pct - body.soc_now_pct) / 100 * usable / CHARGE_EFF
    pmax = min(v.home_charger_kw, model.max_ac_kw or v.home_charger_kw)
    slots = pd.date_range(plug, dep, freq="15min", inclusive="left")
    if len(slots) == 0:
        raise HTTPException(400, "departure is too soon")
    T = len(slots)
    hours = ((slots - plug.normalize()).total_seconds() / 3600).to_numpy()
    prof = services.typical()
    base = np.array([prof.loc[t.dayofweek, t.hour * 4 + t.minute // 15] for t in slots])

    # coordination: EV load already planned by other drivers in the same district
    other = np.zeros(T)
    t0_utc, t1_utc = slots[0].tz_convert("UTC"), dep.tz_convert("UTC")
    for s in db.query(ChargingSession).filter(ChargingSession.district == user.district,
                                              ChargingSession.status == "planned").all():
        ps = pd.Timestamp(s.plug_in_utc).tz_convert("UTC") if pd.Timestamp(s.plug_in_utc).tzinfo else pd.Timestamp(s.plug_in_utc, tz="UTC")
        if ps > t1_utc or ps + pd.Timedelta(minutes=15 * len(json.loads(s.plan_kw_json))) < t0_utc:
            continue
        for k, kw in enumerate(json.loads(s.plan_kw_json)):
            idx = int(((ps + pd.Timedelta(minutes=15 * k)) - t0_utc) / pd.Timedelta("15min"))
            if 0 <= idx < T:
                other[idx] += kw / N_HOMES_FEEDER

    r = lp.plan_single(hours, base, other, need, pmax, 0, T)
    blocks = lp.windows(r["p_kw"])
    fmt = lambda i: slots[i].strftime("%H:%M") if i < T else dep.strftime("%H:%M")
    delivered = need - r["unmet_kwh"]
    soc_at_dep = body.soc_now_pct + 100 * delivered * CHARGE_EFF / usable
    sess = ChargingSession(
        vehicle_random_id=v.random_id, district=user.district, plug_in_utc=plug.tz_convert("UTC").to_pydatetime(),
        departure_utc=dep.tz_convert("UTC").to_pydatetime(), soc_start_pct=body.soc_now_pct,
        soc_target_pct=body.soc_target_pct, kwh_needed=round(need, 3),
        planned_start_utc=slots[blocks[0][0]].tz_convert("UTC").to_pydatetime() if blocks else None,
        planned_end_utc=(slots[blocks[-1][1] - 1] + pd.Timedelta(minutes=15)).tz_convert("UTC").to_pydatetime() if blocks else None,
        plan_kw_json=json.dumps(np.round(r["p_kw"], 3).tolist()), cost_lkr=round(r["cost_lkr"], 1),
        uncontrolled_cost_lkr=round(r["uncontrolled_cost_lkr"], 1))
    db.add(sess); db.commit(); db.refresh(sess)
    return {
        "session_id": sess.id, "vehicle": f"{model.make} {model.model}",
        "windows": [{"start": fmt(a), "end": fmt(b)} for a, b in blocks],
        "plug_in": plug.strftime("%a %H:%M"), "departure": dep.strftime("%a %H:%M"), "departure_source": dep_source,
        "kwh_from_grid": round(need, 2), "charger_kw": pmax, "soc_at_departure_pct": round(min(soc_at_dep, 100), 1),
        "ready": r["unmet_kwh"] < 0.05, "cost_lkr": round(r["cost_lkr"], 0),
        "uncontrolled_cost_lkr": round(r["uncontrolled_cost_lkr"], 0),
        "saving_lkr": round(r["uncontrolled_cost_lkr"] - r["cost_lkr"], 0),
        "timeline": [{"time": t.strftime("%H:%M"), "plan_kw": round(float(p), 2), "uncontrolled_kw": round(float(u), 2),
                      "price": float(pr), "home_load_kw": round(float(b), 3)}
                     for t, p, u, pr, b in zip(slots, r["p_kw"], r["uncontrolled_kw"], r["price"], base)],
        "note": "Home load = typical Sri Lankan household profile (RECON-SL); efficiency 90 % assumed.",
    }


@router.get("/sessions", response_model=list[SessionOut])
def my_sessions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = [v.random_id for v in db.query(Vehicle).filter(Vehicle.user_id == user.id).all()]
    return db.query(ChargingSession).filter(ChargingSession.vehicle_random_id.in_(ids)).order_by(
        ChargingSession.plug_in_utc.desc()).limit(50).all()


# ------------------------------------------------------------------ grid / models (public)
@router.get("/grid/forecast-dates")
def forecast_dates():
    return services.forecast_dates()


@router.get("/grid/forecast")
def grid_forecast(date: str = Query(..., description="YYYY-MM-DD from /grid/forecast-dates")):
    try:
        df = baseload.forecast_day(services.forecast_model(), services.series(), date)
    except ValueError as e:
        raise HTTPException(400, str(e))
    d = df.dropna()
    err = lambda col: float((d["actual_kw"] - d[col]).abs().mean())
    return {"date": date, "points": df.where(df.notna(), None).to_dict(orient="records"),
            "mae_forecast": round(err("forecast_kw"), 4), "mae_last_week": round(err("last_week_kw"), 4)}


@router.get("/grid/scenario")
def grid_scenario(n_ev: int = Query(200, ge=10, le=1000), n_homes: int = Query(1000, ge=100, le=5000),
                  date: str | None = None):
    dates = services.forecast_dates()
    day = date if date in dates else dates[len(dates) // 2]
    t0 = pd.Timestamp(day + " 12:00", tz=TZ)
    idx = pd.date_range(t0, periods=96, freq="15min").tz_convert("UTC")
    base = services.series().reindex(idx).interpolate(limit_direction="both").to_numpy()
    out = scenario.run_scenario(base, n_homes, n_ev, services.real_session_kwh(), shared_config.SEED)
    return {"date": day, "n_ev": n_ev, "n_homes": n_homes, **out}


@router.get("/models/accuracy")
def model_accuracy():
    return services.accuracy()
