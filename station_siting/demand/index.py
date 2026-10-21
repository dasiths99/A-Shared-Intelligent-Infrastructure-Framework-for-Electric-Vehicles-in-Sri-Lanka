"""H3 grid + temporal demand index (models 2.0 / 2.1) and candidate-site criteria (2.4 inputs).

Needs the geo libraries (geopandas, h3, rasterio) - used by database/seed.py, not by the API at runtime.
⚠️ PERIOD_WEIGHTS are assumptions until Sri Lankan survey / pilot data is available.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

M = 5235
RES_H3 = 8
PERIODS = ["weekday_peak", "weekday_offpeak", "weekend_peak", "weekend_offpeak"]
PERIOD_HOURS = {"weekday_peak": 20, "weekday_offpeak": 100, "weekend_peak": 8, "weekend_offpeak": 40}
ROAD_W = {"motorway": 5, "trunk": 4, "primary": 3, "secondary": 2, "tertiary": 1.5, "unclassified": 0.7,
          "residential": 0.5, "living_street": 0.3}
PERIOD_WEIGHTS = pd.DataFrame({
    "population": [0.40, 0.15, 0.30, 0.20], "traffic_proxy": [0.15, 0.20, 0.10, 0.15],
    "poi_office": [0.02, 0.18, 0.00, 0.02], "poi_education": [0.00, 0.08, 0.00, 0.02],
    "poi_health": [0.03, 0.05, 0.03, 0.05], "poi_food": [0.12, 0.06, 0.15, 0.08],
    "poi_entertainment": [0.06, 0.01, 0.08, 0.04], "poi_mall": [0.06, 0.05, 0.12, 0.10],
    "poi_supermarket": [0.06, 0.05, 0.08, 0.10], "poi_bank": [0.00, 0.05, 0.00, 0.02],
    "poi_worship": [0.02, 0.01, 0.04, 0.08], "poi_hotel": [0.04, 0.03, 0.05, 0.05],
    "poi_transport_hub": [0.02, 0.05, 0.02, 0.04], "commercial_share": [0.02, 0.03, 0.03, 0.05],
}, index=PERIODS)
CAND_CATS = ["fuel_station", "supermarket", "mall", "car_park", "hotel", "rest_area"]


def build(processed: Path) -> dict[str, pd.DataFrame]:
    import geopandas as gpd
    import h3
    import rasterio
    import shapely

    district = gpd.read_parquet(processed / "district.parquet")
    roads = gpd.read_parquet(processed / "osm_roads.parquet")
    pois = gpd.read_parquet(processed / "osm_pois.parquet")
    landuse = gpd.read_parquet(processed / "osm_landuse.parquet")
    gss = gpd.read_parquet(processed / "ceb_gss_capacity_2013plan.parquet")
    chargers = gpd.read_parquet(processed / "existing_chargers_osm.parquet")
    dist = district.geometry.iloc[0]

    cells = h3.geo_to_cells(dist.buffer(0.01).__geo_interface__, RES_H3)
    hexes = gpd.GeoDataFrame({"h3": list(cells)}, geometry=[shapely.Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)]) for c in cells], crs=4326)
    hexes = hexes[hexes.geometry.centroid.within(dist)].reset_index(drop=True)
    hm = hexes.to_crs(M)
    hexes["area_km2"] = hm.area / 1e6
    hexes["x"], hexes["y"] = hm.centroid.x.values, hm.centroid.y.values
    H = hexes.set_index("h3")

    with rasterio.open(processed / "worldpop_2020_colombo.tif") as r:
        pop = r.read(1); nod = r.nodata
        rr, cc = np.where((pop > 0) & (pop != nod))
        xs, ys = rasterio.transform.xy(r.transform, rr, cc)
    pc = pd.Series(pop[rr, cc]).groupby([h3.latlng_to_cell(y, x, RES_H3) for x, y in zip(xs, ys)]).sum()
    H["population"] = pc.reindex(H.index).fillna(0)
    p = pois[pois.in_district].copy()
    p["h3"] = [h3.latlng_to_cell(g.y, g.x, RES_H3) for g in p.geometry]
    counts = p.groupby(["h3", "category"]).size().unstack(fill_value=0).reindex(H.index, fill_value=0)
    for c in counts.columns:
        H[f"poi_{c}"] = counts[c]
    rx = gpd.overlay(roads[["road_class", "geometry"]].to_crs(M), hexes[["h3", "geometry"]].to_crs(M), how="intersection")
    rx["w_len_km"] = rx.length / 1000 * rx.road_class.map(ROAD_W).fillna(0.3)
    H["traffic_proxy"] = rx.groupby("h3")["w_len_km"].sum().reindex(H.index).fillna(0)
    lx = gpd.overlay(landuse[landuse.landuse.isin(["commercial", "retail"])][["geometry"]].to_crs(M), hexes[["h3", "geometry"]].to_crs(M), how="intersection")
    H["commercial_share"] = (lx.groupby("h3").apply(lambda d: d.area.sum()) / (H["area_km2"] * 1e6)).reindex(H.index).fillna(0).clip(0, 1)
    W = PERIOD_WEIGHTS.div(PERIOD_WEIGHTS.sum(axis=1), axis=0)
    for c in W.columns:
        if c not in H:
            H[c] = 0.0
    norm = H[W.columns].apply(lambda s: s / s.max() if s.max() > 0 else s)
    for per in PERIODS:
        H[f"D_{per}"] = (norm * W.loc[per]).sum(axis=1)
    H["D_temporal"] = sum(H[f"D_{p}"] * PERIOD_HOURS[p] for p in PERIODS) / sum(PERIOD_HOURS.values())
    H["D_static"] = norm["population"]

    cand = pois[pois.in_district & pois.category.isin(CAND_CATS)].copy().reset_index(drop=True)
    cand["h3"] = [h3.latlng_to_cell(g.y, g.x, RES_H3) for g in cand.geometry]
    cand = cand[cand.h3.isin(H.index)].reset_index(drop=True)
    cm = cand.to_crs(M)
    ring = lambda c, col: H[col].reindex(list(h3.grid_disk(c, 1))).fillna(0).sum()
    for col in ["D_temporal", "D_static", *[f"D_{p}" for p in PERIODS]]:
        cand[col.replace("D_", "demand_")] = [ring(c, col) for c in cand.h3]
    major = roads[roads.road_class.isin(["motorway", "trunk", "primary"])].to_crs(M)
    cand["dist_major_road_m"] = gpd.sjoin_nearest(cm[["geometry"]], major[["geometry"]], distance_col="d").groupby(level=0)["d"].min().values
    g = gss[gss.geometry.notna() & gss.serves_study_area].to_crs(M).reset_index(drop=True)
    nn = gpd.sjoin_nearest(cm[["geometry"]], g[["ceb_name", "spare_2025_mva", "geometry"]], distance_col="d_gss")
    nn = nn[~nn.index.duplicated()]
    cand["gss"], cand["gss_spare_mva"], cand["dist_gss_m"] = nn["ceb_name"].values, nn["spare_2025_mva"].values, nn["d_gss"].values
    ex = chargers[chargers.in_study_area].to_crs(M)
    cand["dist_charger_m"] = gpd.sjoin_nearest(cm[["geometry"]], ex[["geometry"]], distance_col="d").groupby(level=0)["d"].min().values
    cand["site_area_m2"] = cand["site_area_m2"].fillna(0)
    cand["commercial_share"] = H["commercial_share"].reindex(cand.h3).values
    cand["traffic_proxy"] = H["traffic_proxy"].reindex(cand.h3).values
    cand["x"], cand["y"] = cm.geometry.x.values, cm.geometry.y.values
    cand["lat"], cand["lon"] = cand.geometry.y.values, cand.geometry.x.values

    hexes_out = hexes.drop(columns="geometry").merge(
        pd.DataFrame(H.drop(columns=["area_km2", "x", "y", "geometry"])).reset_index(), on="h3")
    hexes_out["geojson"] = [shapely.to_geojson(gm) for gm in hexes.geometry]
    gl = gss[gss.geometry.notna()].copy()
    gl["lat"], gl["lon"] = gl.geometry.y, gl.geometry.x
    ch = chargers.copy(); ch["lat"], ch["lon"] = ch.geometry.y, ch.geometry.x
    return {"hexes": pd.DataFrame(hexes_out), "candidates": pd.DataFrame(cand.drop(columns="geometry")),
            "substations": pd.DataFrame(gl.drop(columns="geometry")), "chargers": pd.DataFrame(ch.drop(columns="geometry")),
            "district_geojson": shapely.to_geojson(dist)}
