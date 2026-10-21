"""Folder locations for C3 data. Raw files (own + shared) are read-only inputs."""

from pathlib import Path

C3_ROOT = Path(__file__).resolve().parent.parent
PROJECT = C3_ROOT.parent
RAW = C3_ROOT / "data" / "raw"
SHARED_RAW = PROJECT / "shared" / "data" / "raw"
INTERIM = C3_ROOT / "data" / "interim"
PROCESSED = C3_ROOT / "data" / "processed"
RESULTS = C3_ROOT / "results"

BMW_DIR = RAW / "bmw_i3_tum"
BMW_SIM_DIR = RAW / "bmw_i3_tum_simulation"
VED_STATIC_EV = RAW / "VED" / "Data" / "VED_Static_Data_PHEV&EV.xlsx"
EVED_GIT_DIR = RAW / "eVED"
EVED_BLOB = "b8cbfe9e24d22f46485e03ca2c2e303d77343efa"  # data/eVED.zip inside the eVED git repo
EVED_ZIP = INTERIM / "eved" / "eVED.zip"  # copy extracted from git (raw stays untouched)
DEM_DIR = RAW / "elevation_copernicus_dem"
WEATHER_DIR = RAW / "weather_open_meteo"
OPEN_EV_JSON = SHARED_RAW / "vehicles" / "open_ev_data.json"
