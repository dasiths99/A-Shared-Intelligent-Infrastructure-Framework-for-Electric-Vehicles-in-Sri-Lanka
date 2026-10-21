"""Extract C2 layers from the Sri Lanka OSM .pbf: roads, POIs, land use, place names.

One pass with pyosmium. Tag filtering runs in C++ (fast); geometry is built only for kept objects.
POIs mapped as areas (malls, car parks ...) become their centroid. OSM data: (c) OpenStreetMap
contributors, ODbL - keep attribution.
"""

from __future__ import annotations

import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import osmium
import shapely
import shapely.wkb

CRS_STORE, CRS_METRIC = "EPSG:4326", "EPSG:5235"

ROAD_CLASSES = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary",
    "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential", "living_street",
}

# (key, value) -> category. 'candidate' = possible charger host site; others = demand attractors.
POI_RULES: list[tuple[str, set[str] | None, str, str]] = [
    ("amenity", {"fuel"}, "fuel_station", "candidate"),
    ("shop", {"supermarket"}, "supermarket", "candidate"),
    ("shop", {"mall", "department_store"}, "mall", "candidate"),
    ("amenity", {"parking"}, "car_park", "candidate"),
    ("tourism", {"hotel"}, "hotel", "candidate"),
    ("highway", {"rest_area", "services"}, "rest_area", "candidate"),
    ("amenity", {"charging_station"}, "existing_charger", "existing"),
    ("office", None, "office", "attractor"),
    ("amenity", {"school", "college", "university"}, "education", "attractor"),
    ("amenity", {"hospital", "clinic"}, "health", "attractor"),
    ("amenity", {"restaurant", "cafe", "fast_food", "food_court"}, "food", "attractor"),
    ("amenity", {"bank"}, "bank", "attractor"),
    ("amenity", {"place_of_worship"}, "worship", "attractor"),
    ("amenity", {"marketplace"}, "market", "attractor"),
    ("amenity", {"cinema", "theatre"}, "entertainment", "attractor"),
    ("amenity", {"bus_station"}, "transport_hub", "attractor"),
    ("railway", {"station"}, "transport_hub", "attractor"),
    ("leisure", {"stadium", "sports_centre"}, "sports", "attractor"),
]
LANDUSE_KEEP = {"residential", "commercial", "retail", "industrial", "farmland", "forest", "grass", "meadow",
                "cemetery", "military", "brownfield", "construction", "recreation_ground", "religious"}
PLACE_KEEP = {"city", "town", "suburb", "quarter", "neighbourhood", "village", "hamlet"}


def classify_poi(tags) -> tuple[str, str] | None:
    for key, values, cat, role in POI_RULES:
        v = tags.get(key)
        if v is not None and (values is None or v in values):
            return cat, role
    return None


def parse_maxspeed(value: str | None) -> float | None:
    """'60' -> 60, '40 mph' -> 64.4, 'signals'/None -> None (km/h)."""
    if not value:
        return None
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(mph)?", value)
    if not m:
        return None
    v = float(m.group(1))
    return round(v * 1.609344, 1) if m.group(2) else v


def _in_box(lon: float, lat: float, box: tuple[float, float, float, float]) -> bool:
    return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]


def extract(pbf: Path, clip_area: shapely.Geometry) -> dict[str, gpd.GeoDataFrame]:
    """Roads, POIs and land use inside `clip_area`; places for all of Sri Lanka (name matching)."""
    box = clip_area.bounds
    wkb = osmium.geom.WKBFactory()
    roads, pois, landuse, places = [], [], [], []
    fp = (osmium.FileProcessor(str(pbf)).with_locations().with_areas()
          .with_filter(osmium.filter.KeyFilter("highway", "amenity", "shop", "tourism", "office",
                                               "railway", "leisure", "landuse", "place")))
    for o in fp:
        tags = o.tags
        try:
            if o.is_node():
                loc = o.location
                if tags.get("place") in PLACE_KEEP and "name" in tags:
                    places.append({"osm_id": f"n{o.id}", "name": tags["name"], "place": tags["place"],
                                   "geometry": shapely.Point(loc.lon, loc.lat)})
                if not _in_box(loc.lon, loc.lat, box):
                    continue
                c = classify_poi(tags)
                if c:
                    pois.append({"osm_id": f"n{o.id}", "category": c[0], "role": c[1], "name": tags.get("name"),
                                 "operator": tags.get("operator") or tags.get("brand"),
                                 "geometry": shapely.Point(loc.lon, loc.lat)})
            elif o.is_way():
                hw = tags.get("highway")
                if hw in ROAD_CLASSES:
                    n0 = o.nodes[0].location
                    if not _in_box(n0.lon, n0.lat, box) and not _in_box(o.nodes[-1].location.lon, o.nodes[-1].location.lat, box):
                        continue
                    roads.append({"osm_id": f"w{o.id}", "highway": hw, "name": tags.get("name"), "ref": tags.get("ref"),
                                  "maxspeed_kmh": parse_maxspeed(tags.get("maxspeed")), "lanes": tags.get("lanes"),
                                  "oneway": tags.get("oneway") == "yes",
                                  "geometry": shapely.wkb.loads(wkb.create_linestring(o), hex=True)})
            elif o.is_area():
                c = classify_poi(tags)
                lu = tags.get("landuse") if tags.get("landuse") in LANDUSE_KEEP else None
                if not c and not lu:
                    continue
                g = shapely.wkb.loads(wkb.create_multipolygon(o), hex=True)
                if not shapely.intersects(g, shapely.box(*box)):
                    continue
                oid = f"{'w' if o.from_way() else 'r'}{o.orig_id()}"
                if c:
                    pois.append({"osm_id": oid, "category": c[0], "role": c[1], "name": tags.get("name"),
                                 "operator": tags.get("operator") or tags.get("brand"), "geometry": g.centroid,
                                 "site_area_m2": None})
                    pois[-1]["_poly"] = g
                if lu:
                    landuse.append({"osm_id": oid, "landuse": lu, "geometry": g})
        except (osmium.InvalidLocationError, RuntimeError, ValueError):
            continue  # broken geometry in OSM (missing nodes / invalid ring) -> skip object

    out = {
        "roads": gpd.GeoDataFrame(roads, crs=CRS_STORE),
        "pois": gpd.GeoDataFrame(pois, crs=CRS_STORE),
        "landuse": gpd.GeoDataFrame(landuse, crs=CRS_STORE),
        "places": gpd.GeoDataFrame(places, crs=CRS_STORE),
    }
    return out


def clean_roads(roads: gpd.GeoDataFrame, clip_area) -> gpd.GeoDataFrame:
    r = roads[roads.geometry.notna() & roads.is_valid]
    r = gpd.clip(r, clip_area)
    r = r[r.geom_type.isin(["LineString", "MultiLineString"])].drop_duplicates("osm_id")
    r["length_m"] = r.to_crs(CRS_METRIC).length
    r = r[r["length_m"] > 0]
    r["road_class"] = r["highway"].str.replace("_link", "", regex=False)
    return r.reset_index(drop=True)


def dedupe_points(gdf: gpd.GeoDataFrame, by: str, dist_m: float = 30) -> tuple[gpd.GeoDataFrame, int]:
    """Same category within `dist_m` = same place mapped twice (e.g. node inside its building area).

    Keeps the first object (areas are listed after nodes, so the node is kept, but the area size is
    copied over when available).
    """
    if gdf.empty:
        return gdf, 0
    m = gdf.to_crs(CRS_METRIC).reset_index(drop=True)
    drop = np.zeros(len(m), dtype=bool)
    for _, idx in m.groupby(by).groups.items():
        idx = np.asarray(idx)
        tree = shapely.STRtree(m.geometry.values[idx])
        i_arr, j_arr = tree.query(m.geometry.values[idx], predicate="dwithin", distance=dist_m)
        for i, j in zip(i_arr, j_arr):
            if j > i and not drop[idx[i]]:
                drop[idx[j]] = True
    return gdf.reset_index(drop=True)[~drop].reset_index(drop=True), int(drop.sum())


def clean_pois(pois: gpd.GeoDataFrame, clip_area) -> tuple[gpd.GeoDataFrame, dict[str, int]]:
    log = {"pois_in": len(pois)}
    if "_poly" in pois:
        poly = gpd.GeoSeries(pois["_poly"], crs=CRS_STORE)
        has = poly.notna()
        pois.loc[has, "site_area_m2"] = poly[has].to_crs(CRS_METRIC).area.values
        pois = pois.drop(columns="_poly")
    p = pois[pois.geometry.within(clip_area)].copy()
    log["outside_area"] = log["pois_in"] - len(p)
    p, n = dedupe_points(p, "category")
    log["duplicates_within_30m"] = n
    log["pois_out"] = len(p)
    return p, log


def clean_landuse(lu: gpd.GeoDataFrame, clip_area) -> gpd.GeoDataFrame:
    lu = lu[lu.is_valid | lu.geometry.notna()].copy()
    lu["geometry"] = lu.geometry.make_valid()
    lu = gpd.clip(lu, clip_area)
    lu = lu[lu.geom_type.isin(["Polygon", "MultiPolygon"])].drop_duplicates("osm_id")
    lu["area_m2"] = lu.to_crs(CRS_METRIC).area
    return lu.reset_index(drop=True)
