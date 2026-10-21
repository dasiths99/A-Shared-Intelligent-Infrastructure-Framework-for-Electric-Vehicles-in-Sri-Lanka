"""Smaller C2 inputs: existing chargers (OSM), rasters (WorldPop, WorldCover), DMT EV registrations."""

from __future__ import annotations

import json
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pdfplumber
import rasterio
import rasterio.mask
import shapely

CRS_STORE = "EPSG:4326"
WORLDCOVER_CLASSES = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built_up", 60: "bare",
                      70: "snow_ice", 80: "water", 90: "wetland", 95: "mangrove", 100: "moss_lichen"}


# ----------------------------------------------------------------------------- chargers
def parse_kw(value: str | None) -> float | None:
    """'22 kW' -> 22, '7.4kW;50 kW' -> 50 (max), None -> None."""
    if not value:
        return None
    nums = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*kw", value.lower())]
    return max(nums) if nums else None


def osm_chargers(json_path: Path) -> gpd.GeoDataFrame:
    el = json.loads(json_path.read_text(encoding="utf-8"))["elements"]
    rows = []
    for e in el:
        t = e.get("tags", {})
        lon, lat = (e["lon"], e["lat"]) if "lon" in e else (e["center"]["lon"], e["center"]["lat"])
        sockets = sorted({k.split(":")[1] for k in t if k.startswith("socket:") and k.count(":") == 1})
        outputs = [parse_kw(v) for k, v in t.items() if k.endswith(":output") or k == "charging_station:output"]
        outputs = [o for o in outputs if o]
        rows.append({
            "osm_id": f"{e['type'][0]}{e['id']}", "name": t.get("name"),
            "operator": t.get("operator") or t.get("network") or t.get("brand"),
            "sockets": ";".join(sockets) or None, "max_kw": max(outputs) if outputs else None,
            "capacity": pd.to_numeric(t.get("capacity"), errors="coerce"),
            "is_dc": any(s in ("type2_combo", "chademo", "gb_dc", "ccs") for s in sockets) or (
                bool(outputs) and max(outputs) >= 25),
            "access": t.get("access"), "fee": t.get("fee"),
            "geometry": shapely.Point(lon, lat)})
    return gpd.GeoDataFrame(rows, crs=CRS_STORE)


# ----------------------------------------------------------------------------- rasters
def clip_raster(src_path: Path, area, out_path: Path) -> dict:
    with rasterio.open(src_path) as src:
        data, transform = rasterio.mask.mask(src, [area], crop=True)
        meta = src.meta | {"height": data.shape[1], "width": data.shape[2], "transform": transform,
                           "compress": "deflate"}
        nodata = src.nodata
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(data)
    return {"file": out_path.name, "width": int(data.shape[2]), "height": int(data.shape[1]), "nodata": nodata}


def raster_sum(path: Path, area) -> float:
    with rasterio.open(path) as src:
        d, _ = rasterio.mask.mask(src, [area], crop=True, filled=False)
    return float(d.sum())


def landcover_share(path: Path, area) -> dict[str, float]:
    with rasterio.open(path) as src:
        d, _ = rasterio.mask.mask(src, [area], crop=True, filled=False)
    v = d.compressed()
    u, n = np.unique(v, return_counts=True)
    return {WORLDCOVER_CLASSES.get(int(k), str(int(k))): round(100 * c / n.sum(), 2) for k, c in zip(u, n)}


def worldcover_tile_for(area, folder: Path) -> Path:
    for f in sorted(folder.glob("*.tif")):
        with rasterio.open(f) as src:
            if shapely.box(*src.bounds).contains(area):
                return f
    raise FileNotFoundError("no single WorldCover tile covers the study area")


# ----------------------------------------------------------------------------- DMT registrations
CLASS_NAMES = ["Motor cars", "Motor Tricycles Van", "Motor Tricycles", "Quadricycle", "Motor Home", "Buses",
               "Motor Cycles", "Dual Purpose Vehicles", "Lorries", "Land Vehicles", "Special Purpose"]
FUEL_RE = re.compile(r"(Diesel/Electric|Petrol/Electric|Electric|Diesel|Petrol|Other)\s+((?:[\d,]+|-)(?:\s+(?:[\d,]+|-)){4})\s*$")


def parse_registrations(pdf_path: Path) -> pd.DataFrame:
    """Table 7.3: new vehicles registered by class and fuel, 2019-2023 (national, DMT)."""
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    rows, cls = [], None
    for line in text.splitlines():
        for c in CLASS_NAMES:
            if c in line:
                cls = c
                break
        m = FUEL_RE.search(line)
        if m and cls:
            vals = [0 if v == "-" else int(v.replace(",", "")) for v in m.group(2).split()]
            rows.append({"vehicle_class": cls, "fuel": m.group(1), **dict(zip(range(2019, 2024), vals))})
    df = pd.DataFrame(rows).drop_duplicates(["vehicle_class", "fuel"])
    df["is_ev"] = df["fuel"] == "Electric"
    df["is_hybrid"] = df["fuel"].str.contains("/Electric")
    return df
