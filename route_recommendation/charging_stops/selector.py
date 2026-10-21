"""Charging-stop planning (model 3.4) with SoC tracking (3.3) - one or more stops.

Repeat until the destination: find where SoC would reach the reserve, pick the best compatible charger
within `max_detour_km` of the route BEFORE that point, charge just enough to reach the destination
(+10 % margin) or to 100 %, continue.
Score = 0.4 later position (uses the battery fully) + 0.3 power + 0.2 short detour + 0.1 not busy
(placeholder 0.5 until the C1 busyness forecast is merged) - 0.1 if the connector is unknown.
Baseline = the charger nearest to the reserve point (first stop).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

DEFAULT_KW = 22.0   # OSM has no power for most chargers -> assumption
CHARGE_EFF = 0.9
MARGIN_PCT = 10.0


def soc_track(e_kwh: np.ndarray, start_soc: float, usable_kwh: float) -> np.ndarray:
    return start_soc - 100 * np.cumsum(e_kwh) / usable_kwh


def compatible(vehicle_conn: str, sockets) -> str:
    if sockets is None or (isinstance(sockets, float) and np.isnan(sockets)) or not str(sockets).strip():
        return "unknown"
    v = set(vehicle_conn.lower().replace("ccs", "type2_combo").split(";"))
    return "yes" if v & set(str(sockets).lower().split(";")) else "no"


def _clean(r: pd.Series, cols) -> dict:
    out = {}
    for k in cols:
        v = r[k]
        if v is None or (isinstance(v, (float, np.floating)) and np.isnan(v)):
            out[k] = None
        elif isinstance(v, (float, np.floating, np.integer)):
            out[k] = round(float(v), 3)
        else:
            out[k] = v
    return out


def plan_stops(route_lat, route_lon, route_km, seg_kwh, start_soc, usable_kwh, reserve, chargers: pd.DataFrame,
               vehicle: dict, max_detour_km: float = 3.0, max_stops: int = 6) -> dict:
    n = len(seg_kwh)
    lat0 = np.radians(np.mean(route_lat))
    d, idx = cKDTree(np.c_[np.asarray(route_lon) * np.cos(lat0), route_lat]).query(np.c_[chargers.lon * np.cos(lat0), chargers.lat])
    c = chargers.assign(detour_km=d * 111.32, seg_idx=idx, route_km=np.asarray(route_km)[idx])
    c["compatible"] = [compatible(vehicle["connector"], s) for s in c.sockets]
    c = c[(c.detour_km <= max_detour_km) & (c.compatible != "no")].copy()
    c["kw"] = c.max_kw.fillna(DEFAULT_KW)
    is_dc = c.kw >= 25
    c["charge_kw"] = np.where(is_dc, np.minimum(c.kw, vehicle.get("max_dc_kw") or 0), np.minimum(c.kw, vehicle.get("max_ac_kw") or 7.4))
    c = c[c.charge_kw > 0]

    soc_profile = np.empty(n)
    stops, nearest, start, soc0, feasible = [], None, 0, float(start_soc), True
    cols = ["osm_id", "name", "operator", "lat", "lon", "route_km", "detour_km", "kw", "charge_kw", "compatible", "score"]
    while True:
        soc = soc0 - 100 * np.cumsum(seg_kwh[start:]) / usable_kwh
        hit = np.flatnonzero(soc <= reserve)
        if not len(hit):
            soc_profile[start:] = soc
            break
        limit = start + int(hit[0])
        cand = c[(c.seg_idx > start) & (c.seg_idx < limit)].copy() if len(stops) < max_stops else c.iloc[0:0]
        if cand.empty:
            soc_profile[start:] = soc
            feasible = False
            break
        nz = lambda s: (s - s.min()) / (s.max() - s.min()) if s.max() > s.min() else s * 0 + 1
        cand["score"] = 0.4 * nz(cand.route_km) + 0.3 * nz(cand.kw) + 0.2 * (1 - nz(cand.detour_km)) + 0.05 - 0.1 * (cand.compatible == "unknown")
        best = cand.sort_values("score", ascending=False).iloc[0]
        if nearest is None:
            nearest = _clean(cand.iloc[(cand.route_km - route_km[limit]).abs().argmin()], cols)
        j = int(best.seg_idx)
        soc_profile[start:j + 1] = soc[: j + 1 - start]
        arrive = float(soc_profile[j])
        remaining = float(seg_kwh[j + 1:].sum())
        target = min(100.0, reserve + 100 * remaining / usable_kwh + MARGIN_PCT)
        add_kwh = max(0.0, (target - arrive) / 100 * usable_kwh)
        stop = _clean(best, cols) | {"soc_at_arrival": round(arrive, 1), "charge_to_pct": round(target, 1),
                                     "charge_kwh": round(add_kwh, 2), "charge_min": round(60 * add_kwh / best.charge_kw / CHARGE_EFF)}
        stops.append(stop)
        start, soc0 = j + 1, target
        if start >= n:
            break
    return {"needed": bool(stops) or not feasible, "feasible": feasible, "stops": stops, "nearest_first": nearest,
            "reserve_km": float(route_km[np.flatnonzero(soc_track(seg_kwh, start_soc, usable_kwh) <= reserve)[0]])
            if (soc_track(seg_kwh, start_soc, usable_kwh) <= reserve).any() else None,
            "soc_profile": soc_profile, "charge_min": int(sum(s["charge_min"] for s in stops)),
            "arrival_soc": float(soc_profile[-1])}
