# J26-IT-430 – Datasets and Models (C1, C2, C3)

For each component: **which datasets** (with download links), **which models** (method, data, baseline,
result) and a **short description** of each model. Results are from the training notebooks run on 19 Oct 2026
(test split, never used for training). Full numbers: each component's `results/` folder.

| Component | Training notebook | Model code (packages) | App |
| --- | --- | --- | --- |
| C1 Charging scheduling | `charging_scheduling/notebooks/c1_model_training.ipynb` | `forecasting/`, `scheduler/`, `simulator/` | Smart Charge LK (`run_c1.bat`) |
| C2 Station siting | `station_siting/notebooks/c2_model_training.ipynb` | `demand/`, `mcdm/`, `mclp/` | GridSite Planner (`run_c2.bat`) |
| C3 Route & charging stop | `route_recommendation/notebooks/c3_model_training.ipynb` | `routing/`, `energy/`, `charging_stops/` | TerrainRoute (`run_c3.bat`) |

---

## C1 – Personalized, Routine-Aware EV Charging Scheduling (*When should each EV charge?*)

### Datasets

| Dataset | What it gives | Link | Used for | Licence |
| --- | --- | --- | --- | --- |
| **ACN-Data** (Caltech, JPL, office001) | 66,745 EV charging sessions 2018–2021 with drivers' app inputs (requested kWh, departure) | https://ev.caltech.edu/dataset | 1.1b EV demand, 1.2 routines, 1.3 need prediction | free token, site terms |
| **Utrecht office parking** (4TU) | 55,379 sessions 2020–2024, one office car park | https://doi.org/10.4121/80ef3824-3f5d-4e45-8794-3b8791efbd13.v1 | 1.2 routines, energy values for the scenario | CC BY-NC-SA 4.0 (non-commercial) |
| **City of Boulder** EV sessions | 67,599 public sessions 2018–2023 (after removing duplicates) | https://open-data.bouldercolorado.gov/datasets/95992b3938be4622b07f0b05eba95d4c_0/about | extra session data (replaces withdrawn Palo Alto) | city open data |
| **UrbanEV** (Shenzhen, Dryad) | 1,682 stations / 275 zones, hourly occupancy, energy, prices | https://datadryad.org/dataset/doi:10.5061/dryad.np5hqc04z | station busyness (later) | Dryad (CC0) |
| **RECON-SL** (Sri Lanka, LIRNEasia) | 15-min smart-meter data of ~2,900 Sri Lankan homes, Oct 2023 – Dec 2024 + surveys | https://ieee-dataport.org/node/14951 (DOI 10.21227/n1dk-q860) | 1.1a base-load forecast, scheduler base load | IEEE DataPort terms |
| **PUCSL tariff table** (Oct 2025) | TOU periods and LKR/kWh | https://www.pucsl.gov.lk/wp-content/uploads/2025/10/Annex-2-Approved-Tariff-Table.pdf | cost of every plan | public |
| PUCSL generation report / 2012 demand-curve study | national demand shape (charts) | https://www.pucsl.gov.lk | background only | public |

### Models

| # | Model | Method | Baseline | Result (test) |
| --- | --- | --- | --- | --- |
| 1.1a | Household base-load forecast | XGBoost, day-ahead, 15-min | same time last week / yesterday | **94.1 %** accuracy (last week 90.2 %, yesterday 94.3 %) |
| 1.1b | EV charging demand forecast | XGBoost, day-ahead, 15-min | same time last week / yesterday | **68.7 %** (last week 54.3 %, yesterday 38.1 %) |
| 1.2 | Routine clustering | K-Means (elbow + silhouette) | – | 1,016 drivers, k = 2, silhouette 0.47 |
| 1.3 | Need prediction (departure + kWh) | XGBoost + quantile q10 | profile defaults, driver app input | departure error **86 min** (default 102); energy error **3.9 kWh** (default 7.3); q10 coverage 87 % |
| 1.4 | Coordinated scheduler | Linear programme (SciPy HiGHS): min peak, then fill low-load slots | B1 uncontrolled, B2 TOU 22:30, B3 TOU + delay, B4 no personal info | peak **−63 %** vs B1, 100 % cars ready; B2 makes a **+46 % rebound peak**; B4 only 49.5 % ready |
| 1.5 | EV data simulator | Monte Carlo | – | scenarios / demos only (never accuracy) |

**Short descriptions**
- **1.1a Base-load forecast** – predicts how much electricity an average Sri Lankan home will use in every 15 minutes of tomorrow, using only data at least 24 h old (yesterday, last week, time of day, weekday). Very accurate, but the simple "same time yesterday" is just as good.
- **1.1b EV demand forecast** – the same idea for the total charging power of a group of chargers; harder to predict, here XGBoost is clearly better than the baselines.
- **1.2 Routine clustering** – groups drivers by habits (arrival time, how regular, how long they stay, kWh, weekend use). With workplace data only 2 weak groups appear; home routines need Sri Lankan pilot data.
- **1.3 Need prediction** – at plug-in, predicts when the car will leave and how much energy it needs, from the driver's own past sessions. A "safe early" (q10) departure keeps the car ready. New drivers (< 10 sessions) use profile defaults (cold start).
- **1.4 Coordinated scheduler** – decides how much power each car gets in each 15-min slot so the street's peak stays as low as possible while every car is ready on time. Shows why "everyone at 22:30" is bad (rebound peak).
- **1.5 Simulator** – creates example home-charging evenings for "what if" scenarios.

---

## C2 – Grid-Aware Temporal MCDM Optimization of Charging Station Locations (*Where to build?*)

### Datasets

| Dataset | What it gives | Link | Used for | Licence |
| --- | --- | --- | --- | --- |
| **OpenStreetMap Sri Lanka** (Geofabrik) | roads, POIs (fuel, malls, supermarkets, car parks, hotels, offices …), land use | https://download.geofabrik.de/asia/sri-lanka.html | demand index, candidate sites, road access | ODbL – attribution |
| **WorldPop 2020** (100 m) | population per cell | https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/LKA/lka_ppp_2020.tif (portal: https://hub.worldpop.org) | demand index | CC BY 4.0 |
| **ESA WorldCover 2021** (10 m) | land cover | https://esa-worldcover.org/en | land suitability | CC BY 4.0 |
| **HDX admin boundaries** (cod-ab-lka) | district / DS / GN polygons | https://data.humdata.org/dataset/cod-ab-lka | study area (Colombo District) | CC BY-IGO |
| **CEB Long Term Transmission Development Plan 2013–2022** | grid substation capacity (MVA) + forecast load to 2025 | https://www.pucsl.gov.lk/wp-content/uploads/2019/09/Transmission-Plan-2013-2022.pdf | **substation capacity constraint** | public |
| **OSM power + chargers** (Overpass extract) | substation locations (141), existing chargers (66) | https://overpass-api.de | grid distance, existing chargers | ODbL |
| **DMT Statistical Abstract 2024, Table 7.3** | new vehicles by fuel 2019–2023 | https://www.statistics.gov.lk/abstract2024/CHAP7/7.3.pdf | EV growth scenarios | public |
| RDA traffic counts · current CEB substation loading · operator charger lists | – | **request via supervisor** | traffic, grid, validation | – |

### Models

| # | Model | Method | Baseline | Result (test / Colombo District) |
| --- | --- | --- | --- | --- |
| 2.0 | Hexagon grid | H3 resolution 8 (~0.78 km²) | – | 866 hexagons |
| 2.1 | Temporal demand index | weighted sum of population, POIs, road traffic proxy, land use per period | static demand (population only) | 4 periods + time-weighted mix |
| 2.2 | Hotspots | K-Means vs DBSCAN | – | K-Means k = 3, silhouette 0.41; DBSCAN finds 1 continuous zone |
| 2.3 | Criteria weights | AHP (eigenvector, consistency ratio) | equal weights | demand 40 %, grid 24 %, road 14 %, competition 14 %, land 8 %; **CR 0.007** |
| 2.4 | Site scoring | weighted-sum MCDM on 1,129 real buildable sites | static MCDM | ranked sites |
| 2.5 | Site selection | **MCLP with substation capacity** (MILP, SciPy HiGHS) | traffic-only top-N, K-Means centres, static MCDM, MCLP without grid | **84.3 % demand covered, 0 overloaded substations** (no-grid 85.3 % / 1 overload; K-Means centres 77.9 %; static MCDM 18.4 %; traffic-only 14.8 %) |
| Val. | Validation | grid stress test, hold-out, ±20 % weights | – | stays at 0 overloads up to 6 MW stations (no-grid: 8 overloads); hold-out hit rate 50 % vs 14 %; top-10 overlap ≥ 90 %, Kendall τ ≥ 0.96 |

**Short descriptions**
- **2.0 Hexagon grid** – cuts Colombo District into equal hexagons so every area is compared fairly.
- **2.1 Temporal demand index** – estimates where EV charging is needed in each period (weekday evening peak, weekday day, weekend …) from people, places and roads. ⚠ Period weights are assumptions until survey/pilot data.
- **2.2 Hotspots** – finds clusters of high demand; used to understand the city, not to place chargers directly.
- **2.3 AHP weights** – turns "how much more important is A than B" judgements into criteria weights and checks they are consistent. ⚠ Placeholder judgements until expert interviews.
- **2.4 Site scoring** – gives every real candidate site (fuel station, mall, supermarket, car park, hotel, rest area) a score from demand, grid spare capacity, road access, land and distance to existing chargers.
- **2.5 MCLP + grid** – chooses the N sites that cover the most demand within 3 km **without overloading any substation** (EV allowance = spare capacity × 0.9 × 20 % ⚠ assumption). Main result: ignoring the grid looks slightly better on coverage but overloads substations.

---

## C3 – Terrain- and SoC-Aware Route and Charging-Stop Recommendation (*Which route and stop?*)

### Datasets

| Dataset | What it gives | Link | Used for | Licence |
| --- | --- | --- | --- | --- |
| **BMW i3 real driving cycles** (TU Munich) | 70 real trips, 1,358 km, 10 Hz: speed, elevation, battery V/I/SoC, heating | https://ieee-dataport.org/open-access/battery-and-heating-data-real-driving-cycles | **training/testing energy models** | IEEE DataPort terms |
| BMW i3 simulation runs (same page) | 24 simulated runs (−10/0/+10 °C) | same link | physics checks only (never accuracy) | same |
| **VED** (Vehicle Energy Dataset, Michigan) | 383 vehicles incl. 3 Nissan Leaf EVs + 24 PHEVs | https://github.com/gsoh/VED | backup of eVED | Apache-2.0 |
| **eVED** (extended VED) | VED + map-matching, smoothed elevation, speed limits, intersections | https://bitbucket.org/datarepo/eved-dataset | **training/testing energy models (Leaf)** | Apache-2.0 |
| **Copernicus DEM GLO-30** | 30 m elevation for all of Sri Lanka | https://registry.opendata.aws/copernicus-dem/ | road slope / climb | Copernicus licence |
| **Open-Meteo archive** | hourly temperature + humidity 2023–2025, 8 towns | https://open-meteo.com/en/docs/historical-weather-api | temperature input | CC BY 4.0 |
| **Open EV Data** | battery size, AC/DC power, connectors, consumption (118 models, 2020) | https://github.com/OpenChargingCloud/open-ev-data | vehicle specs, constant kWh/km baseline | see repo licence |
| **OpenStreetMap Sri Lanka** + OSM chargers | road network (routing), 66 chargers | https://download.geofabrik.de/asia/sri-lanka.html | routes, charging stops | ODbL |

### Models

| # | Model | Method | Baseline | Result (test trips) |
| --- | --- | --- | --- | --- |
| 3.1 | Physics energy model | vehicle dynamics (rolling, drag, grade, acceleration, regen + temperature-based auxiliaries); 8 parameters fitted on training trips | constant kWh/km | BMW **91.7 %**, Leaf **87.9 %** trip accuracy (constant: 76.7 % / 65.2 %) |
| 3.2 | **Hybrid energy model** | physics + XGBoost on the remaining error | physics-only, ML-only | BMW **91.6 %** (best per segment, 5.3 Wh error); Leaf **89.2 %** (best overall, also on hills) |
| 3.3 | Routing + SoC tracking | own router on OSM major roads (643k nodes, 26,882 km, DEM elevation): Dijkstra for **shortest / fastest / energy-aware** | shortest, fastest | Colombo → Kandy 116 km, 12.7 kWh (BMW i3), < 1 s per request |
| 3.4 | Charging-stop planning | multi-stop rule scoring (position, kW, detour, connector, busyness placeholder) | nearest compatible charger | finds stops on Colombo routes; long / hill trips **not reachable with the 66 OSM chargers** |

**Short descriptions**
- **3.1 Physics model** – calculates the energy of each ~200 m road piece from the forces on the car (tyres, air, climbing, speeding up, energy back when braking) plus heater/AC. The car's mass and drag area are not in any dataset, so they are **fitted** on training trips (results match real cars: i3 ≈ 1,550 kg, CdA 0.62 m²).
- **3.2 Hybrid model** – adds an XGBoost correction for what physics misses (driving style, traffic, temperature). About 90 % trip accuracy vs 65–77 % for a constant kWh/km. ⚠ Trained on flat roads (Munich, Michigan) – hill accuracy needs Sri Lankan pilot trips.
- **3.3 Router + SoC** – finds three real road routes and tracks the battery along each one against the 15 % reserve, so the driver sees where a climb uses energy and where braking downhill gives it back.
- **3.4 Stop planner** – if the battery would fall below the reserve, picks the best compatible charger before that point (one or more stops) and how long to charge. Busyness will come from C1 after merging.

---

## Common rules behind all results
- Training and testing on **real data**, **time-based splits** (no shuffling across time); simulators only for scenarios.
- Every proposed model is compared with its **baseline** (`extra document/claude/CLAUDE.md` §6).
- ⚠ = assumption that must be replaced when real data arrives (expert AHP judgements, POI period weights, EV share of substation capacity, CEB current loading, charger list, Sri Lankan pilot trips).
- Keep data attributions: OSM (ODbL), WorldPop / WorldCover / Open-Meteo (CC BY 4.0); Utrecht 4TU is non-commercial.
