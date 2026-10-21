# C1 – Personalized, Routine-Aware EV Charging Scheduling

**Question:** *When* should each EV charge?
**Owner:** Pitadeniya A P I U (IT23310650)

Everything for C1 lives in this folder. Use only `shared/` (config, vehicle list, DB schema) and the API schemas to talk to C2 / C3.

## Folders

| Folder | What goes here | Model # |
| --- | --- | --- |
| `simulator/` | Monte Carlo EV data simulator – **scenarios and demos only, never for accuracy** | 1.5 |
| `forecasting/` | Grid + EV demand forecast, 24 h ahead, 15-min slots (LSTM / GRU / XGBoost) | 1.1 |
| `routine/` | Routine learning, K-Means routine types | 1.2 |
| `need_prediction/` | Departure time + kWh need (XGBoost / RF + quantile), cold start | 1.3 |
| `scheduler/` | Coordinated LP / QP scheduler, rolling 24 h horizon | 1.4 |
| `baselines/` | B1 uncontrolled, B2 fixed TOU 22:30, B3 TOU + random delay, B4 coordinated without personalization, seasonal-naive forecast, profile defaults | – |
| `tests/` | pytest tests | – |
| `notebooks/` | Exploration only | – |
| `results/` | Config + metrics of every experiment | – |
| `data/raw/` | Original downloaded files (never edit) | – |
| `data/interim/`, `data/processed/` | Cleaned data | – |

## Datasets (`data/raw/`) – status 18 Oct 2026

| Folder | Dataset | Status |
| --- | --- | --- |
| `acn_data/` | ACN-Data via REST API (token in `.env`): caltech 31,424 sessions (2018-04-25 → 2021-09-14, 52 % with userInputs), jpl 33,638 (2018-09-05 → 2021-09-14, 94 % userInputs), office001 1,683 (2019-03 → 2021-09). Fields: connection/disconnect/doneCharging time, kWhDelivered, userID, stationID, userInputs (kWhRequested, requestedDeparture, minutesAvailable…) | ✅ downloaded 19 Oct 2026, no duplicates, no zero-kWh. Note **COVID-19 drop from Mar 2020** – keep in mind for time-based splits |
| `utrecht_4tu/` | Utrecht office parking, 55k sessions + survey + README (CC BY-NC-SA, non-commercial) | ✅ downloaded 19 Oct 2026 |
| `boulder/` | City of Boulder (Colorado) public charging sessions 2018+, ~148k rows: station, start/end time, duration, charging time, kWh, port type (L2/DC) | ✅ downloaded 19 Oct 2026 – **replaces Palo Alto** (withdrawn: ORNL export has 0 records, city portal 404) |
| `urbanev/` | UrbanEV Shenzhen, Dryad v2026-02-04 (`UrbanEVDataset.zip` 320 MB, not yet unzipped + `README.md`). 1 Sep 2022 – 28 Feb 2023: **station-raw** 1,682 stations at 5-min (busy/idle piles fast & slow, service fee, electricity price, duration, kWh) + 22,650 piles with kW and AC/DC + station lat/lon; **zone-cleaned** 275 zones at 5-min and 1-hour (occupancy, duration, volume, prices) + adjacency/distance + weather | ✅ added 19 Oct 2026 (zip test OK, 1,701 files). Good for station **busyness forecast** (C1 → C3) |
| `recon_sl/` | RECON-SL Sri Lankan households (5.3 GB): smart meter 15-min (Oct 2023–Dec 2024, ~45.6 M readings) + 6-hour (2023–2024), monthly bills (4,063 homes, 20 months), 3 survey waves (incl. `w3_awareness_of_time_of_use.csv`, billing, appliances). Cumulative kWh → difference per meter to get 15-min load. See `recon_sl/readme.md` | ✅ (added 19 Oct 2026). `data_dictionary.csv` and survey data profilers mentioned in readme are **not included** |

**RECON-SL 6-hour files – extra columns:** `BRANCH`, `DEPOT` (CEB areas: Moratuwa, Nugegoda, Kalutara, Kelaniya, Galle, Kotte, Negombo), anonymised `substation_ID` (815 transformers, no coordinates), and **TR1/TR2/TR3 import registers (most likely kWh per TOU period – confirm with the data dictionary)** for 2,950 homes. Useful for C1 (TOU behaviour) and for C2 (load per transformer area – but not capacity, not mappable).

Also used (in `shared/data/raw/documents/`): PUCSL tariff Oct 2025, PUCSL generation report, PUCSL 2012 demand curve study.

## Cleaned training data (19 Oct 2026)

Run `python -m charging_scheduling.data_prep.run_all`. Details, columns and splits: [charging_scheduling__data_prep__README.md](charging_scheduling__data_prep__README.md).
Report with rows removed per rule: `results/data_prep_report.json`. Raw files verified unchanged after cleaning.

| File (`data/processed/`) | Rows | train / val / test |
| --- | --- | --- |
| `ev_sessions_clean.parquet` | 189,606 (ACN 66,629 · Utrecht 55,378 · Boulder 67,599) | time-based per source; ACN COVID period excluded |
| `ev_users_summary.parquet` | drivers with ID (shared IDs removed) | – |
| `recon_baseload_15min.parquet` | 35,712 slots, median 1,380 households/slot, Oct 2023 – Dec 2024 | 22,343 / 6,815 / 6,554 |
| `recon_monthly_clean.parquet` | 100,928 | – |
| `urbanev_zone_hourly.parquet` | 1,194,600 (275 zones) | 807,400 / 204,600 / 182,600 |
| `../interim/recon_household_15min.parquet` | 45,462,326 household intervals (2,931 homes) | – |

Base-load check: evening peak 18:00–23:00 local (matches PUCSL peak 18:30–22:30), ~9 kWh/day per household,
**76 days with no data** inside the range – forecasting code must handle gaps (no guessing).

## App: Smart Charge LK (backend + database + frontend)

Light, mobile-style **driver app** (teal/green, bottom tabs: Plan · My EV · History · Grid).

| Part | Where | Port |
| --- | --- | --- |
| Backend (FastAPI) | `backend/app/` – routes in `routers.py`, API docs at `/docs` | 8001 |
| Database (SQLite → PostgreSQL via `C1_DATABASE_URL`) | `database/c1.db` – `users` (login only) · `vehicle_models` · `vehicles` (random_id) · `charging_sessions` (random_id + district only) | – |
| Frontend (React + Vite + Recharts) | `frontend/` | 5181 |

```
python -m pip install -r backend-requirements.txt        # once (project root)
.\charging_scheduling\start.ps1                           # opens http://localhost:5181
```

Or simply double-click in this folder: **`setup_c1.bat`** once (creates C1's own Python 3.11 environment in this folder: `.venv`, installs `requirements.txt` + frontend packages, notebook kernel "Python (J26 C1)", prepares missing data / models / database, runs the tests), then **`run_c1.bat`** (start) and **`stop_c1.bat`** (stop).

Features: register (district + consent, no name/plate), add EV from model list (or a brochure model, e.g. BYD),
**plan tonight's charge** (cheapest + least-busy 15-min slots before departure, departure learned after 10 sessions,
coordinated with other drivers' plans in the district), history & savings, household-load forecast vs actual,
scheduler scenario (B1–B4 vs coordinated), model accuracy table, delete-my-data (PDPA).
Model code used by the app: `forecasting/baseload.py`, `scheduler/lp.py`, `simulator/scenario.py`.

## Rules

- Train/test on **real** data only; time-based splits; `SEED` from `shared/config.py`.
- Models read only `charging_sessions` (random_id, district level) – never login data.
- Scheduling slot = 15 min; store UTC, display Asia/Colombo.
