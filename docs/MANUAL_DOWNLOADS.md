# J26-IT-430 – How to download all datasets

## Step 1 – Run the script (downloads everything that is free)

1. Install Python 3.9+ and Git.
2. Open a terminal in the folder where you saved `download_datasets.py`.
3. Run:

```
pip install requests acnportal pytz
python download_datasets.py
```

Everything is saved into a new folder `J26-IT-430_datasets/`. Total size is roughly 1.5–3 GB (the eVED repository is the largest). Re-running skips files that already exist. A `download_log.csv` shows what succeeded or failed.

| Folder | Downloaded automatically |
| --- | --- |
| `shared/osm/` | OpenStreetMap Sri Lanka (roads, POIs, substations) |
| `shared/vehicles/` | Open EV Data – battery, charging power, connectors |
| `shared/documents/` | PUCSL tariff table (Oct 2025), generation report, 2012 demand curve study, vehicle registrations table |
| `shared/boundaries/` | Sri Lanka admin boundaries (HDX) |
| `shared/chargers/` | Open Charge Map Sri Lanka (needs free key – Step 2) |
| `C1_charging_scheduling/` | ACN-Data (needs free token – Step 2), Palo Alto sessions, Utrecht 4TU sessions, UrbanEV Shenzhen |
| `C2_station_siting/` | WorldPop Sri Lanka 2020, ESA WorldCover 2021 tiles |
| `C3_route_recommendation/` | VED, eVED, Copernicus DEM 30 m tiles, hourly temperature for 8 towns (2023–2025) |

## Step 2 – Free keys (then run the script again)

| Key | Get it at | Set it (Windows / macOS-Linux) |
| --- | --- | --- |
| ACN-Data token | https://ev.caltech.edu/register | `set ACN_API_TOKEN=...` / `export ACN_API_TOKEN=...` |
| Open Charge Map key | https://openchargemap.org/site/develop/api | `set OCM_API_KEY=...` / `export OCM_API_KEY=...` |

## Step 3 – Download in your browser (free IEEE account needed)

| Dataset | Link | Save into |
| --- | --- | --- |
| BMW i3 real driving cycles (C3) | https://ieee-dataport.org/open-access/battery-and-heating-data-real-driving-cycles | `C3_route_recommendation/bmw_i3_tum/` |
| RECON-SL Sri Lankan households (C1, ~1 GB) | https://ieee-dataport.org/open-access/residential-electricity-consumption-dataset-sri-lanka-recon-sl | `C1_charging_scheduling/recon_sl/` |

## Step 4 – Request through your supervisor (not openly published)

- **RDA traffic counts** for Colombo District and the chosen expressway (C2).
- **CEB grid substation capacity / loading** for the study area (C2).
- **Charger lists** from Volt Charge, chargeNET and other operators (C2, C3).
- **More PUCSL daily generation reports** if C1 needs more days: https://www.pucsl.gov.lk

## Licences to note

- Utrecht 4TU data: CC BY-NC-SA 4.0 (non-commercial).
- OSM: ODbL (attribution). WorldPop, WorldCover, Open-Meteo: CC BY 4.0.
- Palo Alto and UrbanEV: no clear licence stated – check before publishing results.
- IEEE DataPort datasets: read the licence in each readme.

## If a download fails

Links can change. Open the dataset page listed in the Project Guide (Section 9) and download it in your browser into the same folder.
