# Decision History (from the planning conversation, Oct 2026)

Summary of the planning chat with Claude. Record new decisions at the bottom with date, decision and reason. Supervisor approval is still needed for items marked (S).

## Review of original documents (13–14 Oct 2026)

Issues found in the TAF and original proposals:
- TAF references inconsistent between sections; C2 "temporal" claim not delivered; C1 privacy novelty weak.
- C3 dropped terrain although the TAF promises it; C3 had unfinished placeholders, "DevIntel" copy-paste, inconsistent supervisor names, circular evaluation, undefined metrics.
- C2 had "Pull Request Intelligence" copy-paste, ChatGPT notes in references, wrong Figure 1 labels, mixed appendix numbering, no ground truth for accuracy.
- Group-level: no shared data schema, Gantt/budget not harmonized, ethics needed for user studies.

## Component 1 decisions

| Decision | Reason |
| --- | --- |
| Option B chosen: forecast-driven **coordinated scheduling** (not federated learning) | Matches TAF wording ("off-peak schedules", "grid load optimization"); low data risk; clear before/after load curve; fixed TOU creates rebound peak |
| Add mobile app with registration + vehicle profile (auto-filled from model list) + preferences | Scheduler needs real vehicle details; enables pilot |
| No access to vehicle onboard systems now → **simulated EV data** for scenarios + pluggable data layer (telematics/OBD-II/OCPP later) + manual SoC entry | Manufacturer permission not available; honest design |
| Train/test on real public data only; simulator only for scenarios/demo | Avoid circular evaluation |
| Add **routine learning** (owner habits) + personal need prediction + cold start | Personalized recommendations; RQ2 |
| Privacy-separated database; login data separate; pseudonymous IDs | Keep TAF privacy promise; PDPA |
| Drop RL; LP/QP scheduler | Scope |

## Component 2 decisions

| Decision | Reason |
| --- | --- |
| Combine A (real candidate sites + MCLP) + B light (4 periods + growth scenarios from C1) + C (open data) + D (hold-out, coverage, sensitivity) | Fixes non-buildable cluster centres, adds optimization novelty, makes "temporal" real, solves data and ground-truth gaps |
| H3 hexagons as analysis unit | Equal cells, fast maps |
| Substation capacity as hard MCLP constraint | Grid feasibility |
| Study area: Colombo District + one expressway corridor (S) | Scope |
| EPSG:5235 for distances | Correct metres |

## Component 3 decisions

| Decision | Reason |
| --- | --- |
| Combine A (hybrid physics + XGBoost residual) + B (OSRM alternatives, SoC feasibility, busyness-aware stops) + C (VED/eVED + pilot, typical speeds, C1 busyness) + D (held-out real trips, Sri Lankan test routes, ABRP check) | Works with limited data, honest about real-time data, explainable |
| **Restore terrain** | Approved TAF promises it; hill country matters |
| Scope: intercity > 50 km, 3–4 EV models | Range matters most there |
| Add BMW i3 TUM dataset | VED has only 3 EVs |

## Group decisions

| Decision | Reason |
| --- | --- |
| **Shared EV owner data collection** (survey 50–150, pilot 10–20, optional experts) under one consent + one ethics application | Real Sri Lankan evidence for all three; cheaper |
| Shared vehicle list, DB, API, time periods, coordinate system | Real integration |
| Human effort budget harmonized at LKR 100,000 each | Consistency |
| Timeline Jul 2026–Jun 2027; integration Mar–Apr 2027 | Aligned Gantt charts |

## Data findings (17 Oct 2026)

- Free sources verified; .gov.lk and data hosts not reachable from Claude's cloud workspace → `scripts/download_datasets.py` runs on the team's own computers.
- PUCSL tariff updated 15 Oct 2025 – C1 proposal tariff numbers must be updated.

## New decisions

| Date | Decision | Reason | Supervisor OK? |
| --- | --- | --- | --- |
| 22 Oct 2026 | **Changes golden rule 8 ("never commit data") for the private GitHub repo:** processed data (~330 MB, files ≥ 90 MB via Git LFS) + `c2.db`, `c3.db`, `c1_seed.db` are committed. Raw/interim data (~9 GB) and `c1.db` (real user accounts) stay out | Teammates can run apps/notebooks right after cloning; raw data too big for GitHub and licence-restricted; privacy rule for login data | **ask supervisor** (dataset licences) |
| 18 Oct 2026 | Each component (`charging_scheduling/`, `station_siting/`, `route_recommendation/`) is a self-contained folder with its own `data/`, `tests/`, `notebooks/`, `results/`; data used by 2+ components in `shared/data/raw/`; docs moved to `docs/` | Team develops C1, C2, C3 separately; one owner per folder | n/a (internal) |
| 19 Oct 2026 | Each component gets its own **backend (FastAPI) + database (SQLite, PostgreSQL-ready) + frontend (React + Vite)** with a clearly different design; ports C1 8001/5181, C2 8002/5182, C3 8003/5183. Model code moved from notebooks into packages | Team develops parts separately; Docker/PostgreSQL/Flutter not installed; web apps run now | n/a |
| 19 Oct 2026 | C3 app routes on its **own OSM road graph** (643k nodes, DEM elevation, shortest / fastest / energy-aware Dijkstra) instead of OSRM | No Docker for OSRM; energy-aware routing needs elevation on edges anyway | n/a |
| 19 Oct 2026 | **C1, C2, C3 developed separately – no integration until the team says "merge".** Cross-component inputs (C1 busyness → C3, C1 growth → C2) use local placeholders for now | Team decision: build and test each part on its own first | n/a |
| 19 Oct 2026 | C3 cleaned data built (`route_recommendation/data_prep/`): energy target = battery V×I per ~200 m segment; **eVED used instead of VED** (superset with elevation, speed limits); BMW split by time **within each season**; PHEV segments only when electric-only; simulation kept for physics checks only | Golden rules 2, 3; plain time split would test winter on a summer-only model | n/a |
| 19 Oct 2026 | C2 cleaned layers built (`station_siting/data_prep/`). **Substation capacity for MCLP = CEB LTTDP 2013–2022 Tables 3.1/3.2 (2025 forecast)** until current CEB data arrives; spare = capacity − √(MW²+MVAr²); ±20 % sensitivity required. Study area = Colombo District + 5 km buffer (corridor pending) | Only real capacity numbers available; better than a single "typical 2×31.5 MVA" assumption | **ask supervisor** |
| 19 Oct 2026 | C1 cleaned data built (`charging_scheduling/data_prep/`): time-based splits; ACN train/val/test only pre-COVID (Apr 2018 – Feb 2020); Boulder deduplicated (source file has ~70 k duplicate rows); RECON-SL cumulative readings → 15-min kWh, gaps left missing | Golden rules 2, 3; honest handling of source-data problems | n/a |
| 19 Oct 2026 | Palo Alto sessions replaced by **City of Boulder** sessions (C1); Utrecht 4TU, HDX boundary SHP, OSM chargers + substations, CEB LTTDP 2013–2022 downloaded | Palo Alto withdrawn online; Boulder is the same type of public-charging data and used with Palo Alto in the literature | n/a |
| 19 Oct 2026 | RECON-SL added (`charging_scheduling/data/raw/recon_sl/`); BMW i3 TUM simulation runs kept in a separate folder `route_recommendation/data/raw/bmw_i3_tum_simulation/` and used only for physics-model checks / parameters | Real Sri Lankan household load for C1; golden rule 2 (no accuracy on simulated data) | n/a |
| 18 Oct 2026 | BMW i3 TUM dataset added (`route_recommendation/data/raw/bmw_i3_tum/`, 70 trips) | VED has only 3 EVs | n/a |
