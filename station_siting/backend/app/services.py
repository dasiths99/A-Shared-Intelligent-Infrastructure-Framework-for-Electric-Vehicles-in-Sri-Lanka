"""Loads the seeded C2 tables once and runs scoring + MCLP for the API."""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd
from sqlalchemy import text

from station_siting.mclp import solver
from station_siting.mcdm import scoring

from .db import engine

PERIODS = ["weekday_peak", "weekday_offpeak", "weekend_peak", "weekend_offpeak"]
DEMAND_COLS = ["D_temporal", *[f"D_{p}" for p in PERIODS]]


def _read(table: str) -> pd.DataFrame:
    try:
        return pd.read_sql(f"SELECT * FROM {table}", engine)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("C2 database not seeded - run: python -m station_siting.database.seed") from e


@lru_cache
def hexes() -> pd.DataFrame:
    return _read("hexagons")


@lru_cache
def candidates() -> pd.DataFrame:
    return _read("candidates")


@lru_cache
def substations() -> pd.DataFrame:
    return _read("substations")


@lru_cache
def chargers() -> pd.DataFrame:
    return _read("chargers")


@lru_cache
def meta() -> dict:
    with engine.connect() as con:
        return {k: v for k, v in con.execute(text("SELECT key, value FROM meta"))}


@lru_cache
def hex_coverage(radius_m: int):
    c = candidates()
    return solver.coverage_sets(c[["x", "y"]].to_numpy(), hexes()[["x", "y"]].to_numpy(), radius_m)


def allowance(ev_share: float, pf: float) -> dict[str, float]:
    s = substations()
    s = s[s["serves_study_area"].astype(bool)]
    return dict(zip(s["ceb_name"], (s["spare_2025_mva"].clip(lower=0) * pf * ev_share).astype(float)))


def run(p: dict) -> dict:
    c = candidates().copy()
    H = hexes()
    mode = p["demand_mode"]
    dcol_c = "demand_static" if mode == "static" else f"demand_{mode}"
    dcol_h = "D_static" if mode == "static" else f"D_{mode}"
    c["score"] = scoring.score(c, p["weights"], dcol_c)
    allow = allowance(p["ev_share"], p["power_factor"])
    cover = hex_coverage(int(p["radius_m"]))
    res = solver.solve(H[dcol_h].to_numpy(), cover, p["n_sites"], c["score"].to_numpy(),
                       c["gss"].to_numpy() if p["grid_constraint"] else None,
                       allow if p["grid_constraint"] else None, p["station_mw"] if p["grid_constraint"] else None)
    sel = res["selected"]
    xy = lambda d: d[["x", "y"]].to_numpy()
    metrics = solver.evaluate(xy(c.iloc[sel]), H, p["radius_m"], DEMAND_COLS, c["gss"].to_numpy()[sel], allow, p["station_mw"])
    # baselines on the same settings (CLAUDE.md section 6)
    base = {}
    t = c.nlargest(p["n_sites"], "traffic_proxy")
    base["Traffic-only top-N"] = solver.evaluate(xy(t), H, p["radius_m"], DEMAND_COLS, t["gss"], allow, p["station_mw"])
    s = c.assign(s2=scoring.score(c, p["weights"], "demand_static")).nlargest(p["n_sites"], "s2")
    base["Static MCDM top-N"] = solver.evaluate(xy(s), H, p["radius_m"], DEMAND_COLS, s["gss"], allow, p["station_mw"])
    if p["grid_constraint"]:
        r0 = solver.solve(H[dcol_h].to_numpy(), cover, p["n_sites"], c["score"].to_numpy())
        s0 = r0["selected"]
        base["MCLP without grid"] = solver.evaluate(xy(c.iloc[s0]), H, p["radius_m"], DEMAND_COLS, c["gss"].to_numpy()[s0], allow, p["station_mw"])
    sites = c.iloc[sel].sort_values("score", ascending=False)
    cols = ["id", "name", "category", "operator", "lat", "lon", "gss", "gss_spare_mva", "dist_gss_m", "dist_major_road_m",
            "dist_charger_m", "score", dcol_c]
    sites_out = json.loads(sites[cols].rename(columns={dcol_c: "demand"}).round(4).to_json(orient="records"))
    for i, s_ in enumerate(sites_out, 1):
        s_["rank"] = i
    return {"sites": sites_out, "metrics": metrics | {"runtime_s": res["runtime_s"], "solver_status": res["status"],
                                                      "sites_placed": int(len(sel))},
            "baselines": base, "allowance_mw": {k: round(v, 3) for k, v in allow.items()}}
