# C2 – Grid-Aware Temporal Multi-Criteria Optimization of Charging Station Locations

**Question:** *Where* should new chargers be built?
**Owner:** Senanayake S G (IT23289352)

Everything for C2 lives in this folder. Use only `shared/` (config, OSM, boundaries, charger list) and the API schemas to talk to C1 / C3.

## Folders

| Folder | What goes here | Model # |
| --- | --- | --- |
| `hexgrid/` | H3 hexagon grid over Colombo District + expressway corridor | – |
| `demand/` | Temporal demand index per hexagon × 4 periods × growth scenarios | 2.1 |
| `hotspots/` | K-Means + DBSCAN hotspots | 2.2 |
| `candidates/` | Real buildable sites from OSM (fuel, malls, supermarkets, car parks, rest areas) | – |
| `mcdm/` | AHP weights (CR < 0.1) + weighted sum / TOPSIS site scoring | 2.3, 2.4 |
| `mclp/` | MCLP with substation capacity constraint (PuLP + CBC) | 2.5 |
| `webmap/` | Leaflet / Kepler.gl map, CSV / GeoJSON export | – |
| `baselines/` | Traffic-only top-N, K-Means centres only, static MCDM, MCLP without grid constraint | – |
| `tests/`, `notebooks/`, `results/` | Tests, exploration, experiment outputs | – |
| `data/raw/` | Original downloaded files (never edit) | – |

## Datasets (`data/raw/`) – status 18 Oct 2026

| Folder | Dataset | Status |
| --- | --- | --- |
| `worldpop/` | WorldPop Sri Lanka 2020, 100 m (CC BY 4.0) | ✅ |
| `worldcover/` | ESA WorldCover 2021, 10 m (CC BY 4.0) | ✅ 5/6 tiles (N03E081 is sea) |
| `osm_power/` | OSM Overpass extract 19 Oct 2026: 141 substations (≈55 with voltage: 132 kV, 220/132 kV, 33 kV; 65 named) + 221 power plants. **No capacity (MVA) tags** | ✅ locations only |
| `ceb/` | `CEB_LTTDP_2013-2022.pdf` – CEB Long Term Transmission Development Plan 2013–2022 (via PUCSL). Old; may list grid substations + demand forecast – contents not yet checked | ⚠️ fallback only. Current capacity/loading: ❌ request via supervisor (needed for MCLP constraint) |
| `rda/` | RDA traffic counts | ❌ request via supervisor. No open AADT dataset exists online; fallbacks: OSM road class, JICA CoMTrans report counts, UoM ADT model |

Also used (in `shared/data/raw/`): OSM Sri Lanka ✅, admin boundaries ✅ (`lka_admin_boundaries.shp.zip`, adm0–adm4), DMT registrations PDF ✅, chargers ⚠️ (OSM: 66 sites only – incomplete).

## Cleaned data (19 Oct 2026)

Run `python -m station_siting.data_prep.run_all` (geo libraries: `requirements.txt`). Details: [station_siting__data_prep__README.md](station_siting__data_prep__README.md).
Report: `results/data_prep_report.json`. Raw files (C2 + shared) verified unchanged after cleaning. 11 tests pass.

| Layer (`data/processed/`) | Result for Colombo District |
| --- | --- |
| Study area | 688.2 km², 13 DS divisions, 557 GN divisions (+ 5 km buffer) |
| Roads | 5,406 km (motorway 58, trunk 152, primary 476, secondary 106, tertiary 394, residential 3,449 …) |
| POIs | 6,174 after cleaning (616 duplicates removed). **Candidate sites:** 141 fuel stations, 339 supermarkets, 50 malls, 412 car parks, 253 hotels, 3 rest areas. Attractors: offices 874, food 1,002, education 547 … |
| Population 2020 (WorldPop) | 2,387,016 |
| Land cover (WorldCover) | tree 68 % (home gardens), built-up 24 %, crop 3 %, water 2 % |
| **Grid substations (CEB 2013 plan)** | 95 parsed; 80 located (37 OSM exact, 5 fuzzy, 38 OSM place ≈); **30 serve the study area** (≤ 15 km): 2,530 MVA capacity, 1,636 MVA forecast peak 2025, **895 MVA spare** |
| Existing chargers (OSM) | 66 in Sri Lanka, 22 in the district – incomplete |
| EV registrations (DMT, national) | new EVs 757 (2019), 340, 276, 746, 2,183 (2023) |

**Assumptions to state:** substation capacity/load = CEB *2013 forecast for 2025*, not measured; 38 substation
locations are approximate (place-name centroid); Madampe and one more name were ambiguous → left without location.

## App: GridSite Planner (backend + database + frontend)

Dark **planning dashboard** (slate sidebar, full-screen dark map, amber demand hexagons).

| Part | Where | Port |
| --- | --- | --- |
| Backend (FastAPI) | `backend/app/` – API docs at `/docs` | 8002 |
| Database (SQLite → PostgreSQL/PostGIS via `C2_DATABASE_URL`) | `database/c2.db` – `hexagons` · `candidates` · `substations` · `chargers` · `meta` · `optimization_runs` | – |
| Frontend (React + Vite + Leaflet) | `frontend/` | 5182 |

```
<geo-python> -m station_siting.database.seed   # once: builds c2.db from data/processed (geo libraries)
.\station_siting\start.ps1                       # opens http://localhost:5182
```

Or simply double-click in this folder: **`setup_c2.bat`** once (creates C2's own Python 3.11 environment in this folder: `.venv`, installs `requirements.txt` + frontend packages, notebook kernel "Python (J26 C2)", prepares missing data / models / database, runs the tests), then **`run_c2.bat`** (start) and **`stop_c2.bat`** (stop).

Features: demand map per period, existing chargers, CEB substations (capacity / spare), AHP judgements with live
consistency ratio, MCLP with/without substation limit, comparison with traffic-only / static MCDM / no-grid
baselines, saved runs, CSV / GeoJSON export. Model code: `demand/index.py`, `mcdm/ahp.py`, `mcdm/scoring.py`, `mclp/solver.py`.

## Rules

- Store WGS84 (EPSG:4326); compute distances/areas in SLD99 (EPSG:5235).
- Periods: `weekday_peak`, `weekday_offpeak`, `weekend_peak`, `weekend_offpeak`.
- Keep OSM (ODbL), WorldPop / WorldCover (CC BY 4.0) attribution.
