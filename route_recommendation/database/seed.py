"""Build C3 data for the API. Run ONCE with the geo environment:

    python -m route_recommendation.database.seed

1. Road graph from the Sri Lanka OSM .pbf (motorway ... tertiary + links), elevation for every node from the
   Copernicus DEM, largest connected network only -> data/processed/road_graph_{nodes,edges}.parquet
2. c3.db: vehicles (physics parameters fitted in the C3 training notebook + Open EV Data specs),
   chargers (OSM), places (towns for the search box). trip_logs is created by the API.
OSM data (c) OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

C3 = Path(__file__).resolve().parents[1]
PROJECT = C3.parent
PROC = C3 / "data" / "processed"
DEM_DIR = C3 / "data" / "raw" / "elevation_copernicus_dem"
PBF = PROJECT / "shared" / "data" / "raw" / "osm" / "sri-lanka-latest.osm.pbf"
CHARGERS = PROJECT / "shared" / "data" / "raw" / "chargers" / "osm_charging_stations_LK_2026-10-19.json"
OPEN_EV = PROJECT / "shared" / "data" / "raw" / "vehicles" / "open_ev_data.json"
DB_URL = f"sqlite:///{(C3 / 'database' / 'c3.db').as_posix()}"

ROAD = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link",
        "tertiary", "tertiary_link"}
# ⚠️ assumed typical speeds (km/h) when OSM has no maxspeed - no Sri Lankan traffic speed data available
SPEED = {"motorway": 90, "trunk": 50, "primary": 45, "secondary": 40, "tertiary": 35}


def hav(lon1, lat1, lon2, lat2):
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def build_graph():
    import osmium
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    node_id, lons, lats = {}, [], []
    U, V, HW, MS, OW = [], [], [], [], []

    def nid(n):
        k = n.ref
        if k not in node_id:
            node_id[k] = len(lons); lons.append(n.lon); lats.append(n.lat)
        return node_id[k]

    fp = osmium.FileProcessor(str(PBF), osmium.osm.NODE | osmium.osm.WAY).with_locations()
    for w in fp.with_filter(osmium.filter.KeyFilter("highway")):
        if not w.is_way():
            continue
        hw = w.tags.get("highway")
        if hw not in ROAD:
            continue
        try:
            ids = [nid(n) for n in w.nodes]
        except osmium.InvalidLocationError:
            continue
        ms = w.tags.get("maxspeed", "")
        m = re.match(r"(\d+)", ms)
        speed = float(m.group(1)) if m else np.nan
        ow = w.tags.get("oneway") in ("yes", "1", "true") or hw in ("motorway", "motorway_link")
        for a, b in zip(ids[:-1], ids[1:]):
            if a != b:
                U.append(a); V.append(b); HW.append(hw.replace("_link", "")); MS.append(speed); OW.append(ow)
    nodes = pd.DataFrame({"lon": lons, "lat": lats})
    e = pd.DataFrame({"u": U, "v": V, "highway": HW, "maxspeed": MS, "oneway": OW})
    e["length_m"] = hav(nodes.lon.values[e.u], nodes.lat.values[e.u], nodes.lon.values[e.v], nodes.lat.values[e.v])
    e["speed_kmh"] = e["maxspeed"].where(e["maxspeed"].between(15, 110), e["highway"].map(SPEED)).fillna(35)
    e["speed_kmh"] = np.minimum(e["speed_kmh"], e["highway"].map(SPEED).fillna(35) * 1.25)  # limit -> typical
    n = len(nodes)
    g = coo_matrix((np.ones(len(e)), (e.u, e.v)), shape=(n, n))
    _, lab = connected_components(g, directed=False)
    big = np.bincount(lab).argmax()
    keep = lab == big
    new = -np.ones(n, dtype=int); new[keep] = np.arange(keep.sum())
    e = e[keep[e.u] & keep[e.v]].copy(); e["u"], e["v"] = new[e.u], new[e.v]
    nodes = nodes[keep].reset_index(drop=True)
    return nodes, e.drop(columns="maxspeed").reset_index(drop=True)


def add_elevation(nodes: pd.DataFrame) -> pd.Series:
    import rasterio
    out = np.full(len(nodes), np.nan)
    for f in sorted(DEM_DIR.glob("*.tif")):
        with rasterio.open(f) as r:
            b = r.bounds
            m = (nodes.lon >= b.left) & (nodes.lon < b.right) & (nodes.lat >= b.bottom) & (nodes.lat < b.top)
            if not m.any():
                continue
            arr = r.read(1)
            rows, cols = rasterio.transform.rowcol(r.transform, nodes.lon[m].values, nodes.lat[m].values)
            rows = np.clip(np.asarray(rows), 0, arr.shape[0] - 1); cols = np.clip(np.asarray(cols), 0, arr.shape[1] - 1)
            out[m.values] = arr[rows, cols]
    return pd.Series(out).interpolate(limit_direction="both")


def vehicles_table() -> pd.DataFrame:
    runs = sorted((C3 / "results").glob("c3_training_*.json"))
    if not runs:
        raise SystemExit("run notebooks/c3_model_training.ipynb first (needs fitted physics parameters)")
    phys = json.loads(runs[-1].read_text())["metrics"]["3.1_physics_params"]
    run_id = runs[-1].stem.replace("c3_training_", "")
    rows = [
        {"name": "BMW i3 (60 Ah)", "usable_kwh": 18.8, "max_dc_kw": 47.0, "max_ac_kw": 7.4, "connector": "ccs;type2",
         "params_source": f"fitted on 70 real TUM trips (run {run_id})", "hybrid_model": f"bmw_hybrid_residual_{run_id}.json", **phys["bmw"]},
        {"name": "Nissan Leaf 2013 (24 kWh)", "usable_kwh": 24.0, "max_dc_kw": 46.0, "max_ac_kw": 3.6, "connector": "chademo;type1",
         "params_source": f"fitted on eVED Leaf trips (run {run_id})", "hybrid_model": f"eved_hybrid_residual_{run_id}.json", **phys["eved"]},
    ]
    return pd.DataFrame(rows)


def chargers_table() -> pd.DataFrame:
    rows = []
    for e in json.loads(CHARGERS.read_text(encoding="utf-8"))["elements"]:
        t = e.get("tags", {})
        kws = [float(x) for k, s in t.items() if k.endswith("output") for x in re.findall(r"(\d+(?:\.\d+)?)\s*kw", s.lower())]
        socks = sorted({k.split(":")[1] for k in t if k.startswith("socket:") and k.count(":") == 1})
        rows.append({"osm_id": f"{e['type'][0]}{e['id']}", "name": t.get("name"), "operator": t.get("operator") or t.get("network") or t.get("brand"),
                     "lat": e.get("lat") or e["center"]["lat"], "lon": e.get("lon") or e["center"]["lon"],
                     "max_kw": max(kws) if kws else None, "sockets": ";".join(socks) or None})
    return pd.DataFrame(rows)


def places_table() -> pd.DataFrame:
    import osmium
    rows = []
    for n in osmium.FileProcessor(str(PBF), osmium.osm.NODE).with_filter(osmium.filter.KeyFilter("place")):
        if n.tags.get("place") in ("city", "town") and "name" in n.tags:
            rows.append({"name": n.tags.get("name:en") or n.tags["name"], "place": n.tags["place"], "lat": n.location.lat, "lon": n.location.lon})
    return pd.DataFrame(rows).drop_duplicates("name").sort_values("name").reset_index(drop=True)


def main():
    nodes, edges = build_graph()
    nodes["elev_m"] = add_elevation(nodes).round(1)
    nodes.to_parquet(PROC / "road_graph_nodes.parquet", index=False)
    edges.to_parquet(PROC / "road_graph_edges.parquet", index=False)
    eng = create_engine(DB_URL)
    with eng.begin() as con:
        for t in ("vehicles", "chargers", "places"):
            con.execute(text(f"DROP TABLE IF EXISTS {t}"))
    vehicles_table().to_sql("vehicles", eng, index=True, index_label="id")
    chargers_table().to_sql("chargers", eng, index=False)
    places_table().to_sql("places", eng, index=False)
    print(f"graph: {len(nodes):,} nodes, {len(edges):,} edges, {edges.length_m.sum() / 1000:,.0f} km | "
          f"elevation {nodes.elev_m.min():.0f}..{nodes.elev_m.max():.0f} m")


if __name__ == "__main__":
    main()
