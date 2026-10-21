#!/usr/bin/env python3
"""
J26-IT-430 - Shared Intelligent Infrastructure Framework for EVs in Sri Lanka
Download all freely available datasets, organised by component.

Usage (on your own computer, Python 3.9+):
    pip install requests acnportal           # acnportal only needed for ACN-Data
    python scripts/download_datasets.py               # download everything that is free
    python scripts/download_datasets.py --list        # just show what will be downloaded
    python scripts/download_datasets.py --only c3     # one group: shared, c1, c2, c3

Files are saved into each component's own folder:
    shared/data/raw/  charging_scheduling/data/raw/  station_siting/data/raw/  route_recommendation/data/raw/

Optional keys (free registration):
    ACN_API_TOKEN   -> https://ev.caltech.edu/register   (ACN-Data, Component 1)
    OCM_API_KEY     -> https://openchargemap.org/site/develop/api  (charger list, C2/C3)
  Put them in the project .env file (never committed), or:
  Windows:  set ACN_API_TOKEN=xxxx      macOS/Linux:  export ACN_API_TOKEN=xxxx

Already-downloaded files are skipped, so you can re-run safely.
Datasets that need a login in a browser (IEEE DataPort) are listed at the end
and in MANUAL_DOWNLOADS.md.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Please run:  pip install requests")

ROOT = Path(__file__).resolve().parent.parent  # project root
# Each component keeps its own raw data; data used by 2+ components lives in shared/
RAW = {
    "shared": ROOT / "shared" / "data" / "raw",
    "c1": ROOT / "charging_scheduling" / "data" / "raw",
    "c2": ROOT / "station_siting" / "data" / "raw",
    "c3": ROOT / "route_recommendation" / "data" / "raw",
}
LOG = ROOT / "scripts" / "download_log.csv"

# Load keys (ACN_API_TOKEN, OCM_API_KEY) from the project .env file if not already set
_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _k, _sep, _v = _line.partition("=")
        if _sep and not _k.strip().startswith("#") and _v.strip():
            os.environ.setdefault(_k.strip(), _v.strip())
HEADERS = {"User-Agent": "J26-IT-430-research-downloader/1.0"}

# Sri Lanka bounding box (approx.)
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 5.9, 9.9, 79.5, 81.9

results = []  # (group, name, status, path)


# ----------------------------------------------------------------- helpers
def log(group, name, status, path=""):
    results.append((group, name, status, str(path)))
    print(f"[{group}] {status:<8} {name} {path}")


def download(url, dest: Path, group, name, min_bytes=1000):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= min_bytes:
        log(group, name, "exists", dest)
        return True
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=60) as r:
            if r.status_code == 404:
                log(group, name, "missing", url)
                return False
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r   {name}: {done/1e6:.1f}/{total/1e6:.1f} MB", end="")
            print()
        tmp.rename(dest)
        log(group, name, "ok", dest)
        return True
    except Exception as e:  # noqa: BLE001
        if tmp.exists():
            tmp.unlink()
        log(group, name, "FAILED", f"{url} ({e})")
        return False


def git_clone(url, dest: Path, group, name):
    if dest.exists():
        log(group, name, "exists", dest)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], check=True)
        log(group, name, "ok", dest)
    except FileNotFoundError:
        log(group, name, "FAILED", "git is not installed - install git or download in a browser: " + url)
    except subprocess.CalledProcessError as e:
        log(group, name, "FAILED", f"{url} ({e})")


# ----------------------------------------------------------------- SHARED
def shared():
    g, d = "shared", RAW["shared"]
    # OpenStreetMap Sri Lanka (roads, POIs, substations) - used by C2 and C3
    download("https://download.geofabrik.de/asia/sri-lanka-latest.osm.pbf",
             d / "osm" / "sri-lanka-latest.osm.pbf", g, "OpenStreetMap Sri Lanka (~140 MB)")
    # EV specifications (battery, charging power, connectors)
    download("https://raw.githubusercontent.com/OpenChargingCloud/open-ev-data/master/data/ev-data.json",
             d / "vehicles" / "open_ev_data.json", g, "Open EV Data (vehicle specs)", min_bytes=100)
    # Tariff and grid documents (PUCSL)
    pdfs = {
        "PUCSL_Approved_Tariff_Table_Oct2025.pdf":
            "https://www.pucsl.gov.lk/wp-content/uploads/2025/10/Annex-2-Approved-Tariff-Table.pdf",
        "PUCSL_Generation_Report_2024-10-22.pdf":
            "https://www.pucsl.gov.lk/wp-content/uploads/2024/10/Generation-Report-22nd-Oct-2024.pdf",
        "PUCSL_2012_Demand_Curve_Study.pdf":
            "https://www.pucsl.gov.lk/wp-content/uploads/2020/06/2012-STUDY-REPORT-ON-ELECTRICITY-DEMAND-CURVE-AND-SYSTEM-PEAK-REDUCTION.pdf",
        "Statistical_Abstract_2024_Table7.3_New_Vehicles_by_Fuel.pdf":
            "https://www.statistics.gov.lk/abstract2024/CHAP7/7.3.pdf",
    }
    for fn, url in pdfs.items():
        download(url, d / "documents" / fn, g, fn, min_bytes=500)
    # Admin boundaries (HDX CKAN API)
    hdx_dataset(d / "boundaries", g)
    # Existing chargers (Open Charge Map, needs free key)
    ocm(d / "chargers", g)


def hdx_dataset(dest, g):
    api = "https://data.humdata.org/api/3/action/package_show?id=cod-ab-lka"
    try:
        res = requests.get(api, headers=HEADERS, timeout=60).json()["result"]["resources"]
    except Exception as e:  # noqa: BLE001
        log(g, "Sri Lanka admin boundaries (HDX)", "FAILED", f"{api} ({e})")
        return
    for r in res:
        name = r.get("name", "")
        if name.lower().endswith((".shp.zip", "_shp.zip", ".xlsx")):
            download(r["url"], dest / name, g, f"HDX {name}")


def ocm(dest, g):
    key = os.environ.get("OCM_API_KEY")
    name = "Open Charge Map - Sri Lanka chargers"
    if not key:
        log(g, name, "SKIPPED", "set OCM_API_KEY (free) to download")
        return
    url = ("https://api.openchargemap.io/v3/poi?output=json&countrycode=LK"
           f"&maxresults=10000&compact=false&verbose=false&key={key}")
    download(url, dest / "openchargemap_LK.json", g, name, min_bytes=100)
    print("   NOTE: OCM Sri Lanka data is partly outdated - check against operator apps.")


# ----------------------------------------------------------------- C1
def c1():
    g, d = "c1", RAW["c1"]
    acn(d / "acn_data", g)
    # Palo Alto 2011-2020 was withdrawn (ORNL export has 0 records, city portal 404, checked 19 Oct 2026).
    # Replacement: City of Boulder public charging sessions 2018+ (ArcGIS open data, ~148k sessions)
    download("https://opendata.arcgis.com/api/v3/datasets/95992b3938be4622b07f0b05eba95d4c_0/downloads/data"
             "?format=csv&spatialRefId=4326",
             d / "boulder" / "boulder_ev_charging_sessions.csv", g, "Boulder charging sessions (~23 MB)")
    # Utrecht office parking sessions (4TU.ResearchData API)
    fourtu("80ef3824-3f5d-4e45-8794-3b8791efbd13", d / "utrecht_4tu", g)
    # UrbanEV Shenzhen: Dryad API now needs a login (HTTP 401) -> manual browser download, see MANUAL


def acn(dest, g):
    token = os.environ.get("ACN_API_TOKEN")
    name = "ACN-Data sessions"
    if not token:
        log(g, name, "SKIPPED", "set ACN_API_TOKEN (free at ev.caltech.edu/register)")
        return
    try:
        from datetime import datetime
        import pytz
        from acnportal import acndata
    except ImportError:
        log(g, name, "SKIPPED", "pip install acnportal")
        return
    client = acndata.DataClient(token)
    tz = pytz.timezone("America/Los_Angeles")
    start, end = tz.localize(datetime(2018, 4, 25)), tz.localize(datetime(2021, 9, 15))
    dest.mkdir(parents=True, exist_ok=True)
    for site in ["caltech", "jpl", "office001"]:
        out = dest / f"acn_{site}_sessions.json"
        if out.exists():
            log(g, f"ACN {site}", "exists", out)
            continue
        try:
            sessions = list(client.get_sessions_by_time(site, start, end))
            with open(out, "w") as f:
                json.dump(sessions, f, default=str)
            log(g, f"ACN {site} ({len(sessions)} sessions)", "ok", out)
        except Exception as e:  # noqa: BLE001
            log(g, f"ACN {site}", "FAILED", str(e))


def fourtu(uuid, dest, g):
    api = f"https://data.4tu.nl/v2/articles/{uuid}/files"
    try:
        files = requests.get(api, headers=HEADERS, timeout=60).json()
        for f in files:
            download(f["download_url"], dest / f["name"], g, f"4TU {f['name']}")
    except Exception as e:  # noqa: BLE001
        log(g, "Utrecht office parking (4TU)", "FAILED",
            f"open https://doi.org/10.4121/{uuid}.v1 in a browser and click 'download all' ({e})")


# ----------------------------------------------------------------- C2
def c2():
    g, d = "c2", RAW["c2"]
    # WorldPop Sri Lanka 2020, 100 m (single GeoTIFF); fallback = full archive
    ok = download("https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/LKA/lka_ppp_2020.tif",
                  d / "worldpop" / "lka_ppp_2020.tif", g, "WorldPop Sri Lanka 2020 (100 m)")
    if not ok:
        download("https://data.worldpop.org/GIS/Population/Individual_countries/LKA/Sri_Lanka_100m_Population.7z",
                 d / "worldpop" / "Sri_Lanka_100m_Population.7z", g, "WorldPop Sri Lanka archive (308 MB)")
    # ESA WorldCover 2021 v200 - 3x3 degree tiles covering Sri Lanka
    for lat in (3, 6, 9):
        for lon in (78, 81):
            tile = f"N{lat:02d}E{lon:03d}"
            fn = f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
            download(f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/{fn}",
                     d / "worldcover" / fn, g, f"WorldCover {tile}")


# ----------------------------------------------------------------- C3
def c3():
    g, d = "c3", RAW["c3"]
    # VED and eVED (git repositories)
    git_clone("https://github.com/gsoh/VED.git", d / "VED", g, "Vehicle Energy Dataset (VED)")
    git_clone("https://Datarepo@bitbucket.org/datarepo/eved-dataset.git", d / "eVED", g, "eVED (large)")
    # Copernicus DEM 30 m tiles (1x1 degree) over Sri Lanka - sea-only tiles do not exist (404 is fine)
    for lat in range(5, 10):
        for lon in range(79, 82):
            nm = f"Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM"
            download(f"https://copernicus-dem-30m.s3.amazonaws.com/{nm}/{nm}.tif",
                     d / "elevation_copernicus_dem" / f"{nm}.tif", g, f"DEM N{lat}E{lon}")
    # Hourly temperature 2023-2025 for key towns (Open-Meteo archive, free, CC BY 4.0)
    towns = {"Colombo": (6.93, 79.85), "Kandy": (7.29, 80.63), "NuwaraEliya": (6.97, 80.77),
             "Galle": (6.03, 80.22), "Jaffna": (9.66, 80.02), "Kurunegala": (7.49, 80.36),
             "Kegalle": (7.25, 80.35), "Anuradhapura": (8.31, 80.40)}
    for town, (la, lo) in towns.items():
        url = ("https://archive-api.open-meteo.com/v1/archive?"
               f"latitude={la}&longitude={lo}&start_date=2023-01-01&end_date=2025-12-31"
               "&hourly=temperature_2m,relative_humidity_2m&timezone=Asia%2FColombo&format=csv")
        download(url, d / "weather_open_meteo" / f"{town}_hourly_2023_2025.csv", g, f"Weather {town}", min_bytes=100)
        time.sleep(1)


# ----------------------------------------------------------------- manual list
MANUAL = """
MANUAL DOWNLOADS (need a free login in your browser):
 1. BMW i3 real driving cycles (C3)  - https://ieee-dataport.org/open-access/battery-and-heating-data-real-driving-cycles
      -> save into  route_recommendation/data/raw/bmw_i3_tum/      (DONE 18 Oct 2026)
 2. RECON-SL Sri Lanka households (C1) - https://ieee-dataport.org/open-access/residential-electricity-consumption-dataset-sri-lanka-recon-sl
      -> save into  charging_scheduling/data/raw/recon_sl/   (5.3 GB unzipped, DONE 19 Oct 2026)
 3. ACN-Data token (C1)               - https://ev.caltech.edu/register  then set ACN_API_TOKEN and re-run
 4. Open Charge Map key (C2, C3)      - https://openchargemap.org/site/develop/api then set OCM_API_KEY and re-run
 5. More PUCSL daily generation reports (C1) - https://www.pucsl.gov.lk  (one PDF per day)
 6. UrbanEV Shenzhen (C1, 320 MB)    - https://datadryad.org/dataset/doi:10.5061/dryad.np5hqc04z
      -> download UrbanEVDataset.zip into  charging_scheduling/data/raw/urbanev/   (DONE 19 Oct 2026)
NOT OPENLY PUBLISHED (request by letter/email via supervisor):
 - RDA traffic counts (C2)  - Road Development Authority
 - CEB grid substation capacity / loading (C2) - Ceylon Electricity Board
 - Current charger lists from operators (Volt Charge, chargeNET, others) (C2, C3)
"""

GROUPS = {"shared": shared, "c1": c1, "c2": c2, "c3": c3}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=GROUPS.keys())
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        print(__doc__)
        print("Groups:", ", ".join(GROUPS))
        print(MANUAL)
        return
    for key, fn in GROUPS.items():
        if a.only and key != a.only:
            continue
        print(f"\n===== {key.upper()} =====")
        fn()
    with open(LOG, "w") as f:
        f.write("group,dataset,status,path_or_note\n")
        for row in results:
            f.write(",".join('"' + x.replace('"', "'") + '"' for x in row) + "\n")
    print("\nSummary:")
    for s in ("ok", "exists", "SKIPPED", "missing", "FAILED"):
        n = sum(1 for r in results if r[2] == s)
        if n:
            print(f"  {s:<8} {n}")
    print("Log written to", LOG)
    print(MANUAL)


if __name__ == "__main__":
    main()
