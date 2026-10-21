"""Run all C2 cleaning steps.  Usage (from the project root, with the geo environment):

    python -m station_siting.data_prep.run_all

Reads only raw files (station_siting/data/raw + shared/data/raw) - never changed.
Writes GeoParquet / GeoTIFF / CSV to station_siting/data/processed and a report to
station_siting/results/data_prep_report.json. All layers stored in WGS84 (EPSG:4326).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd

from . import osm_layers, other_layers, power, study_area
from .paths import (BOUNDARIES_ZIP, CEB_PDF, DMT_PDF, OSM_CHARGERS_JSON, OSM_PBF, OSM_POWER_JSON, PROCESSED,
                    RESULTS, WORLDCOVER_DIR, WORLDPOP_TIF)

SUBSTATION_SEARCH_M = 15_000  # substations this far outside the district can still feed it


def _save(gdf, name: str) -> dict:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    p = PROCESSED / name
    if name.endswith(".parquet"):
        gdf.to_parquet(p, index=False)
    else:
        gdf.to_csv(p, index=False)
    return {"file": name, "rows": len(gdf), "mb": round(p.stat().st_size / 1e6, 2)}


def main() -> None:
    rep = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "outputs": {}, "cleaning": {},
           "summary": {}, "notes": []}

    def step(name):
        print(f"[{name}] ...", flush=True)
        return time.time()

    # 1 study area ---------------------------------------------------------------------
    t = step("study_area")
    sa = study_area.build(BOUNDARIES_ZIP)
    for k, g in sa.items():
        rep["outputs"][k] = _save(g, f"{k}.parquet")
    district = sa["district"].geometry.iloc[0]
    area = sa["district_buffer"].geometry.iloc[0]
    rep["summary"]["district_area_km2"] = round(float(sa["district"]["area_km2"].iloc[0]), 1)
    rep["summary"]["ds_divisions"] = len(sa["ds_divisions"])
    rep["summary"]["gn_divisions"] = len(sa["gn_divisions"])
    rep["notes"].append("Expressway corridor not yet chosen (supervisor) - only Colombo District + 5 km buffer.")
    print(f"   {time.time() - t:.0f} s", flush=True)

    # 2 OSM layers ---------------------------------------------------------------------
    t = step("osm_layers")
    raw = osm_layers.extract(OSM_PBF, area)
    roads = osm_layers.clean_roads(raw["roads"], area)
    pois, log = osm_layers.clean_pois(raw["pois"], area)
    landuse = osm_layers.clean_landuse(raw["landuse"], area)
    for g in (roads, pois, landuse):
        g["in_district"] = g.geometry.representative_point().within(district)
    rep["cleaning"]["pois"] = log
    rep["outputs"]["roads"] = _save(roads, "osm_roads.parquet")
    rep["outputs"]["pois"] = _save(pois, "osm_pois.parquet")
    rep["outputs"]["landuse"] = _save(landuse, "osm_landuse.parquet")
    rep["summary"]["road_km_in_district_by_class"] = (
        roads[roads.in_district].groupby("road_class")["length_m"].sum().div(1000).round(1).to_dict())
    rep["summary"]["pois_in_district_by_category"] = pois[pois.in_district]["category"].value_counts().to_dict()
    places = raw["places"]
    print(f"   {time.time() - t:.0f} s", flush=True)

    # 3 rasters ------------------------------------------------------------------------
    t = step("rasters")
    rep["outputs"]["worldpop"] = other_layers.clip_raster(WORLDPOP_TIF, area, PROCESSED / "worldpop_2020_colombo.tif")
    rep["summary"]["population_2020_district"] = round(other_layers.raster_sum(WORLDPOP_TIF, district))
    wc = other_layers.worldcover_tile_for(area, WORLDCOVER_DIR)
    rep["outputs"]["worldcover"] = other_layers.clip_raster(wc, area, PROCESSED / "worldcover_2021_colombo.tif")
    rep["summary"]["landcover_district_pct"] = other_layers.landcover_share(wc, district)
    rep["notes"].append("WorldCover maps home gardens as 'tree' - built_up share understates urban area.")
    print(f"   {time.time() - t:.0f} s", flush=True)

    # 4 substations --------------------------------------------------------------------
    t = step("substations")
    subs = power.osm_substations(OSM_POWER_JSON)
    ceb = power.read_ceb_tables(CEB_PDF)
    named = subs[subs["name"].notna()][["name", "geometry"]]
    m1 = power.match_names(ceb, named, fuzzy_cutoff=0.85, prefer_near=district)
    m1["location_source"] = [f"osm_substation_{x}" if g is not None else None for x, g in zip(m1["match"], m1["geometry"])]
    todo = m1["geometry"].isna()
    # fallback: OSM place with the same name (exact only - fuzzy place names gave wrong towns)
    m2 = power.match_names(ceb[todo.values], places[["name", "geometry"]], fuzzy_cutoff=None, prefer_near=district)
    m2["location_source"] = [f"osm_place_{x} (approx.)" if g is not None else
                             ("unlocated_ambiguous_name" if x == "ambiguous" else "unlocated_no_name_match")
                             for x, g in zip(m2["match"], m2["geometry"])]
    loc = pd.concat([m1[~todo], m2], ignore_index=True)
    ceb = ceb.merge(loc, on="ceb_name", how="left")
    ceb = gpd.GeoDataFrame(ceb, geometry="geometry", crs="EPSG:4326")
    near = district if district is not None else area
    metric = gpd.GeoSeries([near], crs="EPSG:4326").to_crs(5235).iloc[0]
    has = ceb.geometry.notna()
    ceb["dist_to_district_km"] = None
    ceb.loc[has, "dist_to_district_km"] = (ceb[has].to_crs(5235).distance(metric) / 1000).round(2).values
    ceb["serves_study_area"] = ceb["dist_to_district_km"].fillna(1e9).astype(float) <= SUBSTATION_SEARCH_M / 1000
    subs["in_district"] = subs.within(district)
    rep["outputs"]["substations_osm"] = _save(subs, "substations_osm.parquet")
    rep["outputs"]["ceb_gss"] = _save(ceb, "ceb_gss_capacity_2013plan.parquet")
    rep["summary"]["ceb_gss_total"] = len(ceb)
    rep["summary"]["ceb_gss_located"] = int(has.sum())
    rep["summary"]["ceb_gss_location_source"] = ceb["location_source"].value_counts().to_dict()
    rep["summary"]["ceb_gss_serving_study_area"] = int(ceb["serves_study_area"].sum())
    rep["summary"]["ceb_gss_unlocated"] = ceb.loc[~has, "ceb_name"].tolist()
    rep["notes"].append("Substation capacity/load = CEB LTTDP 2013-2022 FORECAST for 2025 (assumption, not "
                        "measured). OSM has no capacity tags. Current data requested via supervisor.")
    print(f"   {time.time() - t:.0f} s", flush=True)

    # 5 chargers -----------------------------------------------------------------------
    t = step("chargers")
    ch = other_layers.osm_chargers(OSM_CHARGERS_JSON)
    n = len(ch)
    ch, dup = osm_layers.dedupe_points(ch.assign(_all="x"), "_all")
    ch = ch.drop(columns="_all")
    ch["in_district"] = ch.within(district)
    ch["in_study_area"] = ch.within(area)
    rep["cleaning"]["chargers"] = {"rows_in": n, "duplicates_within_30m": dup, "rows_out": len(ch)}
    rep["outputs"]["chargers"] = _save(ch, "existing_chargers_osm.parquet")
    rep["summary"]["chargers_in_district"] = int(ch["in_district"].sum())
    rep["notes"].append("Existing chargers from OSM are INCOMPLETE (66 sites in Sri Lanka vs 100+ Volt Charge, "
                        "300+ ChargeNET) - hold-out validation needs the operator lists.")
    print(f"   {time.time() - t:.0f} s", flush=True)

    # 6 registrations ------------------------------------------------------------------
    t = step("registrations")
    reg = other_layers.parse_registrations(DMT_PDF)
    rep["outputs"]["registrations"] = _save(reg, "dmt_new_registrations_2019_2023.csv")
    ev = reg[reg["is_ev"]].set_index("vehicle_class")[[2019, 2020, 2021, 2022, 2023]]
    rep["summary"]["new_ev_registrations_national"] = {str(k): v for k, v in ev.sum().items()}
    rep["notes"].append("DMT registrations are national only (no district split) and end in 2023.")
    print(f"   {time.time() - t:.0f} s", flush=True)

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "data_prep_report.json").write_text(json.dumps(rep, indent=2, default=str))
    print(json.dumps({k: rep[k] for k in ("summary", "cleaning", "notes")}, indent=1, default=str))


if __name__ == "__main__":
    main()
