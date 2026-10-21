"""Folder locations for C2 data. Raw files (own + shared) are read-only inputs."""

from pathlib import Path

C2_ROOT = Path(__file__).resolve().parent.parent
PROJECT = C2_ROOT.parent
RAW = C2_ROOT / "data" / "raw"
SHARED_RAW = PROJECT / "shared" / "data" / "raw"
INTERIM = C2_ROOT / "data" / "interim"
PROCESSED = C2_ROOT / "data" / "processed"
RESULTS = C2_ROOT / "results"

OSM_PBF = SHARED_RAW / "osm" / "sri-lanka-latest.osm.pbf"
BOUNDARIES_ZIP = SHARED_RAW / "boundaries" / "lka_admin_boundaries.shp.zip"
OSM_CHARGERS_JSON = SHARED_RAW / "chargers" / "osm_charging_stations_LK_2026-10-19.json"
DMT_PDF = SHARED_RAW / "documents" / "Statistical_Abstract_2024_Table7.3_New_Vehicles_by_Fuel.pdf"
OSM_POWER_JSON = RAW / "osm_power" / "osm_substations_plants_LK_2026-10-19.json"
CEB_PDF = RAW / "ceb" / "CEB_LTTDP_2013-2022.pdf"
WORLDPOP_TIF = RAW / "worldpop" / "lka_ppp_2020.tif"
WORLDCOVER_DIR = RAW / "worldcover"
