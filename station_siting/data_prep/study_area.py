"""Study area: Colombo District (+ DS / GN divisions) from the HDX boundary shapefiles.

Stored in WGS84 (EPSG:4326); buffers and areas computed in SLD99 (EPSG:5235) - golden rule 5.
The expressway corridor is not chosen yet (supervisor) -> add it here later.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pyogrio

CRS_STORE, CRS_METRIC = "EPSG:4326", "EPSG:5235"
DISTRICT = "Colombo"
BUFFER_M = 5_000  # roads/POIs/rasters just outside the border still serve edge hexagons


def read_admin(zip_path: Path, level: int) -> gpd.GeoDataFrame:
    return pyogrio.read_dataframe(f"/vsizip/{zip_path.as_posix()}/lka_admin{level}.shp").to_crs(CRS_STORE)


def build(zip_path: Path) -> dict[str, gpd.GeoDataFrame]:
    """Return district polygon, buffered area, DS divisions (adm3) and GN divisions (adm4)."""
    adm2 = read_admin(zip_path, 2)
    district = adm2[adm2["adm2_name"] == DISTRICT][["adm2_name", "adm2_pcode", "adm1_name", "geometry"]].reset_index(drop=True)
    if len(district) != 1:
        raise ValueError(f"expected one '{DISTRICT}' district, found {len(district)}")
    m = district.to_crs(CRS_METRIC)
    district["area_km2"] = m.area / 1e6
    buffered = gpd.GeoDataFrame({"name": [f"{DISTRICT} + {BUFFER_M / 1000:.0f} km"]},
                                geometry=m.buffer(BUFFER_M).to_crs(CRS_STORE).values, crs=CRS_STORE)
    adm3 = read_admin(zip_path, 3)
    ds = adm3[adm3["adm2_name"] == DISTRICT][["adm3_name", "adm3_pcode", "adm2_name", "geometry"]].reset_index(drop=True)
    ds["area_km2"] = ds.to_crs(CRS_METRIC).area / 1e6
    adm4 = read_admin(zip_path, 4)
    gn = adm4[adm4["adm3_name"].isin(ds["adm3_name"])][["adm4_name", "adm4_pcode", "adm3_name", "geometry"]]
    gn = gn[gn.representative_point().within(district.geometry.iloc[0])].reset_index(drop=True)
    gn["area_km2"] = gn.to_crs(CRS_METRIC).area / 1e6
    return {"district": district, "district_buffer": buffered, "ds_divisions": ds, "gn_divisions": gn}
