# CLAUDE.md – J26-IT-430 EV Framework (read this first)

This file tells Claude Code how to work in this repository. Full background is in `docs/`:
- `docs/PROJECT_CONTEXT.md` – what the project is, each component, research questions, metrics
- `docs/DATASETS.md` – every dataset, what is inside, where it lives, licence
- `docs/DECISIONS.md` – history of decisions and why (from the planning chat)
- `docs/MANUAL_DOWNLOADS.md` – how to download the datasets

## 1. Project in one paragraph

SLIIT IT4010 final-year research project **J26-IT-430**, CoEAI research group:
*"A Shared Intelligent Infrastructure Framework for Electric Vehicles in Sri Lanka."*
One AI platform with three components that share one database, one vehicle list and one API:

| Component | Question | Owner | Folder |
| --- | --- | --- | --- |
| C1 – Personalized, Routine-Aware EV Charging Scheduling | **When** should each EV charge? | Pitadeniya A P I U (IT23310650) | `charging_scheduling/` |
| C2 – Grid-Aware Temporal Multi-Criteria Optimization of Charging Station Locations | **Where** should new chargers be built? | Senanayake S G (IT23289352) | `station_siting/` |
| C3 – Terrain- and SoC-Aware Route and Charging-Stop Recommendation (Hybrid Physics–ML) | **Which route and stop?** | Seniya K A D D (IT23273658) | `route_recommendation/` |

Supervisor / co-supervisor: names must be confirmed by the team (spelling differs between documents) – never invent them.

## 2. Repository layout

```
J26-IT-430/
├── CLAUDE.md                ← this file
├── README.md
├── requirements.txt
├── .gitignore               ← */data/ and secrets are never committed
├── docs/                    ← context, datasets, decisions, download guide
├── scripts/download_datasets.py   ← saves into each component's data/raw/
├── shared/                  ← only what 2+ components need
│   ├── config.py, vehicles/, db/schema.sql
│   └── data/raw/            ← osm, vehicles (Open EV Data), documents (PUCSL, DMT), boundaries, chargers
├── charging_scheduling/     ← C1: simulator/ forecasting/ routine/ need_prediction/ scheduler/ baselines/
├── station_siting/          ← C2: hexgrid/ demand/ hotspots/ candidates/ mcdm/ mclp/ webmap/ baselines/
├── route_recommendation/    ← C3: routing/ segments/ energy/ soc/ charging_stops/ baselines/
├── backend-requirements.txt ← runtime libs of the three backends
├── api/                     ← shared REST API – only after the team says "merge"
└── app/                     ← mobile app (Flutter or React Native) – later
```

Each component also has its **own app** (developed separately until "merge"):
`<component>/backend/app/` (FastAPI) · `<component>/database/` (SQLite, PostgreSQL-ready via
`C1_/C2_/C3_DATABASE_URL`, seed scripts) · `<component>/frontend/` (React + Vite, own design) · `<component>/start.ps1`.

| App | Backend | Frontend | Design |
| --- | --- | --- | --- |
| C1 Smart Charge LK | :8001 | :5181 | light mobile driver app, teal/green |
| C2 GridSite Planner | :8002 | :5182 | dark planning dashboard, slate/amber |
| C3 TerrainRoute | :8003 | :5183 | dark navigation app, indigo/orange |

(Port 5173 is used by another local project – keep `strictPort: true`.)

Each component folder is **self-contained** and developed separately: its own
`data/{raw,interim,processed}/` (NOT in git), `tests/`, `notebooks/` (exploration only),
`results/` and `README.md` (folders + dataset status).

## 3. Golden rules (do not break)

1. **Privacy:** models only ever use pseudonymous `random_id` + **district-level** location. Never store or log names, emails, phone, number plates, VIN, NIC, exact addresses or continuous GPS. Login data lives only in `users` table, separate from `charging_sessions` / `trips`.
2. **No circular evaluation:** ML models are trained and tested on **real** data (ACN-Data, VED/eVED, BMW i3, pilot). The simulator is used **only** for scenarios and demos, never to measure model accuracy.
3. **Time-based splits** for every time-series or behaviour model (no random shuffling across time).
4. **Every proposed method is compared with its baseline** (see section 6). A result without a baseline is not finished.
5. **Coordinates:** store WGS84 (EPSG:4326); compute distances/areas in **SLD99 / EPSG:5235** (metres).
6. **Time:** store UTC, display Asia/Colombo. Scheduling slot = **15 minutes**.
7. **Reproducible:** fixed random seed (`SEED = 42` in `shared/config.py`), pinned requirements, every experiment writes its config + metrics to `results/`.
8. **Never commit data or secrets.** Keys (`ACN_API_TOKEN`, `OCM_API_KEY`) come from environment variables / `.env`.
9. **Licences:** keep attribution for OSM (ODbL), WorldPop, WorldCover, Open-Meteo (CC BY 4.0). Utrecht 4TU data is non-commercial (CC BY-NC-SA).
10. Keep the three components **independent packages** that talk only through `shared/` and the API schemas.

## 4. Shared conventions

- Python 3.11, type hints, `black` + `ruff`, `pytest` tests in each package `tests/`.
- Shared vehicle list: `shared/vehicles/vehicle_list.csv` (make, model, year, usable_kwh, max_ac_kw, max_dc_kw, connector, kwh_per_100km, mass_kg, cda_m2, crr, drivetrain_eff, regen_eff, source). Same list is used by C1 (profile auto-fill) and C3 (physics model).
- Time periods used by all: `weekday_peak`, `weekday_offpeak`, `weekend_peak`, `weekend_offpeak`.
- Tariff (PUCSL, effective 15 Oct 2025): domestic TOU **peak 18:30–22:30 LKR 67/kWh, day 05:30–18:30 LKR 35, off-peak 22:30–05:30 LKR 21**, fixed LKR 2,100/month. EV station tariffs: DC 111/87/53, AC L2 90/70/40 (peak/day/off-peak). Keep in `shared/config.py` – re-check before final results.
- Battery reserve default 15 %. Study area for C2: Colombo District + one expressway corridor (to be chosen with supervisor).
- API: FastAPI, JSON / GeoJSON, endpoints prefixed `/c1`, `/c2`, `/c3`, `/shared`.

## 5. Component summaries (details in docs/PROJECT_CONTEXT.md)

**C1 – When to charge.** App registration + vehicle profile → routine learning (K-Means routine types) → personal need prediction (XGBoost / quantile regression: departure time, kWh; cold start = profile defaults until ~10 sessions) → grid + EV demand forecast (LSTM/GRU/XGBoost, 24 h, 15-min) → **coordinated LP scheduler** (rolling 24 h, minimize Σ(base_load + EV_load)², deadlines, max power, min SoC) → personal charging window. RQ1: beats uncontrolled / fixed TOU (rebound peak)? RQ2: personal predictions beat defaults?

**C2 – Where to build.** H3 hexagons → demand per hexagon per period × growth scenario (C1 forecast) → K-Means & DBSCAN hotspots → real buildable candidate sites from OSM (fuel stations, malls, supermarkets, car parks, rest areas) → AHP-weighted MCDM (demand, road access, grid capacity, land, distance to existing chargers) → **MCLP with substation capacity constraint** (PuLP/CBC) → ranked sites + web map. Validate with hold-out of existing stations, coverage, ±20 % weight sensitivity.

**C3 – Which route and stop.** OSRM alternatives (3–5) on Sri Lanka OSM → ~200 m segments with smoothed DEM slope, road class, typical speed → **hybrid energy = physics (rolling, drag, grade, acceleration, regen) + XGBoost residual** (traffic, AC, driving style) → SoC tracking vs reserve → charging stop by detour, kW, connector, C1 busyness forecast → ranking by energy, time, arrival SoC. Scope: intercity trips > 50 km, 3–4 common EV models. Terrain is IN scope (approved TAF).

## 6. Baselines (must implement)

| Component | Baselines |
| --- | --- |
| C1 | B1 uncontrolled; B2 fixed TOU start 22:30; B3 TOU + random delay; B4 coordinated without personalization; forecast vs seasonal-naive; need prediction vs profile defaults |
| C2 | traffic-only top-N; K-Means centres only; static MCDM (no periods); MCLP without grid constraint |
| C3 | constant kWh/km; physics-only; ML-only; shortest route; fastest route; nearest compatible charger |

## 7. How to work with me (Claude Code)

- Ask which component (C1/C2/C3/shared) a task belongs to if unclear; keep changes inside that package.
- Before writing a model, check `docs/DATASETS.md` for the correct dataset and its fields.
- Prefer small, testable functions; add a test with each new module.
- When adding data loaders, read from `<component>/data/raw/...` (or `shared/data/raw/...`) as listed in `docs/DATASETS.md`; write cleaned outputs to that component's `data/processed/`.
- Explain results in plain, simple English (team members prefer simple explanations).
- Do not fabricate data, results, citations or supervisor names. If data is missing, say so and propose the documented fallback.
- Update `docs/DECISIONS.md` when a design decision changes.

## 8. Current status (Oct 2026)

- Proposals for C1, C2, C3 rewritten (with before/after pages) – stored as Claude Docs; links in `docs/PROJECT_CONTEXT.md`.
- Datasets identified and verified online (17 Oct 2026); download script ready (`scripts/download_datasets.py`).
- Next: agree shared vehicle list + DB schema + API schemas → ethics application → download data → first model versions (C1 forecast, C2 demand index, C3 physics model).
