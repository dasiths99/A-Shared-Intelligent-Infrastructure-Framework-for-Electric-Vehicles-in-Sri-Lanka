# C3 – Terrain- and SoC-Aware Route and Charging-Stop Recommendation (Hybrid Physics–ML)

**Question:** *Which* route and charging stop?
**Owner:** Seniya K A D D (IT23273658)

Everything for C3 lives in this folder. Use only `shared/` (config, vehicle list, OSM, charger list) and the API schemas to talk to C1 / C2.

## Folders

| Folder | What goes here | Model # |
| --- | --- | --- |
| `routing/` | OSRM (Docker) on Sri Lanka OSM, 3–5 alternative routes | 3.3 |
| `segments/` | ~200 m segments, smoothed DEM slope, road class, typical speed | 3.3 |
| `energy/` | Physics model (rolling, drag, grade, acceleration, regen) + XGBoost residual | 3.1, 3.2 |
| `soc/` | SoC tracking against 15 % reserve | 3.3 |
| `charging_stops/` | Stop selection: detour, kW, connector, C1 busyness forecast | 3.4 |
| `baselines/` | Constant kWh/km, physics-only, ML-only, shortest, fastest, nearest charger | – |
| `tests/`, `notebooks/`, `results/` | Tests, exploration, experiment outputs | – |
| `data/raw/` | Original downloaded files (never edit) | – |

## Datasets (`data/raw/`) – status 18 Oct 2026

| Folder | Dataset | Status |
| --- | --- | --- |
| `bmw_i3_tum/` | BMW i3 real driving cycles (TUM): 70 trips, 1,357 km, 10 Hz, V/I/SoC/elevation/heating | ✅ |
| `bmw_i3_tum_simulation/` | **Simulated** BMW i3 runs (TUM vehicle model): ambient −10 / 0 / +10 °C × Standard / Heating / Charging / Mixed × CAN / LIN, `.csv` + `.mat`. Columns incl. slope, wind, traction force, roll resistance coeff, mass, pack V/I, SoC, heater power, kWh/100km | ✅ **Simulation – never use to measure model accuracy** (golden rule 2). OK for: checking our physics model against TUM's, i3 parameters (mass, Crr), heating-power vs temperature |
| `VED/` | Vehicle Energy Dataset (3 Nissan Leaf EVs + 24 PHEVs), `.7z` not yet extracted | ✅ |
| `eVED/` | eVED (VED + map-matching + elevation). `eVED.zip` is inside `.git` – checkout failed on Windows | ⚠️ extract with `git -C eVED show HEAD:data/eVED.zip > eVED.zip` |
| `elevation_copernicus_dem/` | Copernicus DEM 30 m, 12 tiles (the 3 missing are sea-only) | ✅ |
| `weather_open_meteo/` | Hourly temperature + humidity 2023–2025, 8 towns (CC BY 4.0) | ✅ |

Also used (in `shared/`): OSM Sri Lanka ✅, Open EV Data ✅ (2020, no BYD), vehicle mass/CdA/Crr ❌ (spec sheets), chargers ❌.

### BMW i3 loader notes
- `;` separated, Latin-1 encoding, 10 Hz. **6 different header versions** – match columns by name prefix.
- B04 and B09 contain fast-charging stops – remove those parts before energy training.
- SoC gaps in B07 (18 %), B09 (37 %), B34 (60 %) – use V × I for energy. B14 final SoC = 0 (sensor glitch).
- Elevation only 437–665 m (flat) – hills must come from the physics part.

## Cleaned training data (19 Oct 2026)

Run `python -m route_recommendation.data_prep.run_all` (~1.5 min). Details: [route_recommendation__data_prep__README.md](route_recommendation__data_prep__README.md).
Report: `results/data_prep_report.json`. Raw files verified unchanged (214 files). 9 tests pass.

| Table (`data/processed/`) | Rows | train / val / test |
| --- | --- | --- |
| `bmw_segments_200m` (BMW i3, 70 trips, 1,358 km, 223 kWh) | 6,792 segments | 5,019 / 739 / 1,034 (time order within each season) |
| `eved_segments_200m`, `electric_only == True` (3 Leaf + 24 PHEV) | 37,594 segments (EV 11,709 · PHEV 25,885) | 24,127 / 7,124 / 6,343 |
| `bmw_sim_runs` (simulation – checks only) | 917,281 time steps, 24 runs | – |
| `weather_hourly` (8 Sri Lankan towns) | 210,432 hours | – |

Checks: BMW median 13.3 kWh/100 km summer, 19.1 winter; segment median 0.15–0.16 kWh/km in both datasets.
Grades: BMW ±1.5 %, eVED ±5 % (1st–99th percentile) – **flat compared with Sri Lankan hills**.

## App: TerrainRoute (backend + database + frontend)

Dark **navigation app** (indigo night, neon-orange route, glass panels, elevation + battery chart).

| Part | Where | Port |
| --- | --- | --- |
| Backend (FastAPI) | `backend/app/` – API docs at `/docs` | 8003 |
| Database (SQLite → PostgreSQL via `C3_DATABASE_URL`) | `database/c3.db` – `vehicles` (fitted physics params) · `chargers` · `places` · `trip_logs` | – |
| Road graph | `data/processed/road_graph_{nodes,edges}.parquet` – 643k nodes, 26,882 km OSM major roads + DEM elevation | – |
| Frontend (React + Vite + Leaflet + Recharts) | `frontend/` | 5183 |

```
<geo-python> -m route_recommendation.database.seed   # once: road graph + c3.db (geo libraries, ~15 s)
.\route_recommendation\start.ps1                      # opens http://localhost:5183
```

Or simply double-click in this folder: **`setup_c3.bat`** once (creates C3's own Python 3.11 environment in this folder: `.venv`, installs `requirements.txt` + frontend packages, notebook kernel "Python (J26 C3)", prepares missing data / models / database, runs the tests), then **`run_c3.bat`** (start) and **`stop_c3.bat`** (stop).

Features: town search or click-on-map, vehicle + battery + reserve, **3 real road routes** (shortest, fastest,
energy-aware) with energy by constant / physics / hybrid model, climb, battery along the route vs reserve,
**multi-stop charging plan** (compatible connector, detour, kW) vs nearest-charger baseline, ranking.
Model code: `routing/graph.py`, `energy/route_energy.py`, `charging_stops/selector.py`.
Finding: with the 66 OSM chargers, long / hill trips (Jaffna, Nuwara Eliya for the i3) are **not reachable** –
the operator charger lists are needed.

## Rules

- Train/test on **real** trips with time-based splits; simulator never used for accuracy.
- Scope: intercity trips > 50 km, 3–4 EV models. Battery reserve 15 %.
