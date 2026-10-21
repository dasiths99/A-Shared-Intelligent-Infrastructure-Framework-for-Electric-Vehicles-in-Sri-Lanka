# A Shared Intelligent Infrastructure Framework for Electric Vehicles in Sri Lanka

SLIIT IT4010 research project **J26-IT-430** (CoEAI). One AI platform, three components – developed
separately for now, each with its own data pipeline, models, backend, database and web app.

| Component | Question | Folder | App |
| --- | --- | --- | --- |
| **C1** Personalized, Routine-Aware EV Charging Scheduling | *When* should each EV charge? | `charging_scheduling/` | Smart Charge LK – http://localhost:5181 |
| **C2** Grid-Aware Temporal MCDM Charging-Station Siting | *Where* should new chargers be built? | `station_siting/` | GridSite Planner – http://localhost:5182 |
| **C3** Terrain- and SoC-Aware Route & Charging-Stop Recommendation | *Which* route and stop? | `route_recommendation/` | TerrainRoute – http://localhost:5183 |

## Run a component (Windows)

Needs **Python 3.11** and **Node.js LTS**. In the component's folder, double-click:

1. `setup_c1.bat` / `setup_c2.bat` / `setup_c3.bat` – once: creates that part's own `.venv`, installs its
   `requirements.txt` and frontend packages, registers the notebook kernel, prepares missing data/models/database, runs the tests
2. `run_cX.bat` – starts backend + frontend and opens the browser
3. `stop_cX.bat` – stops it

## Data is NOT in this repository

Raw / processed datasets, databases, `.venv` and `node_modules` are excluded (`.gitignore`) – size, licences and
privacy. Download the datasets with `scripts/download_datasets.py` and the manual steps in `docs/MANUAL_DOWNLOADS.md`,
then `setup_cX.bat` rebuilds everything. API keys go in a local `.env` file (never committed).

## Documents

- `docs/MODELS_AND_DATASETS.md` (+ PDF) – every dataset with link, every model with method, baseline and result
- `docs/PROJECT_CONTEXT.md`, `docs/DATASETS.md`, `docs/DECISIONS.md`
- `extra document/` – component READMEs, project instructions (CLAUDE.md) and notes

Data attribution: © OpenStreetMap contributors (ODbL); WorldPop, ESA WorldCover, Open-Meteo (CC BY 4.0);
Utrecht 4TU data is non-commercial (CC BY-NC-SA 4.0).
