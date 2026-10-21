# C3 data preparation – cleaned, training-ready data for the energy model

**Raw data is never changed.** Code only reads `route_recommendation/data/raw/` and `shared/data/raw/`.
The eVED zip is copied out of the git object store into `data/interim/eved/` (raw repo untouched).
C3 only – nothing here is read by C1/C2 until the team decides to merge.

```
python -m route_recommendation.data_prep.run_all              # everything (eVED step takes minutes)
python -m route_recommendation.data_prep.run_all --skip-eved
python -m pytest route_recommendation/tests
```

Geo libraries: `../station_siting/requirements.txt` + `openpyxl`. Report: `results/data_prep_report.json`.

## Folder organisation

```
route_recommendation/data/
├── raw/        ORIGINAL (never edited): bmw_i3_tum/, bmw_i3_tum_simulation/, VED/, eVED/ (git), DEM, weather
├── interim/    eved/eVED.zip (copy from git), eved_ev_phev_rows.parquet (EV/PHEV rows, all signals)
└── processed/  training-ready tables (below)
```

## Output files (`data/processed/`)

| File | One row = | Use for |
| --- | --- | --- |
| `bmw_segments_200m.parquet` | ~200 m piece of a BMW i3 trip | **3.1 physics check, 3.2 XGBoost residual (training table)** |
| `bmw_trips_1hz.parquet` | 1 second of a BMW trip (charging removed) | build other features, plots |
| `bmw_trip_summary.parquet` | one BMW trip: date (UTC), route, weather, km, kWh, kWh/100 km, SoC, season, split | trip-level checks, baselines |
| `eved_segments_200m.parquet` | ~200 m piece of an eVED EV/PHEV trip (+ speed limit, intersections, bus stops) | **second training table** – use `electric_only == True` |
| `eved_ev_trips_1hz.parquet`, `eved_trips.parquet` | 1 s of an eVED trip / one trip | features, plots |
| `bmw_sim_runs.parquet` | TUM simulation time step (24 runs: −10/0/+10 °C × 4 profiles × CAN/LIN) | **physics checks only – never accuracy** |
| `vehicle_params_from_data.csv` | one parameter actually present in the data (Crr, rotating mass, Leaf weight class) | physics model inputs (rest from spec sheets) |
| `vehicle_specs_openev.parquet` | one BEV model: usable kWh, AC/DC kW, ports, consumption | vehicle list draft |
| `weather_hourly.parquet` | town × hour (UTC): temperature, humidity (8 Sri Lankan towns, 2023–2025) | temperature feature for SL trips |
| `dem_tiles_index.parquet` | one Copernicus DEM tile + bounds | `other.sample_elevation()` for route segments |

### Segment columns (both training tables)

`trip_id, seg, t_start_s, duration_s, dist_m, speed_mean_kmh, speed_std_kmh, speed_max_kmh, n_stops, stopped_s,
accel_pos_mean, elev_start_m, elev_end_m, elev_change_m, grade_pct, energy_kwh (target), energy_traction_kwh,
energy_regen_kwh, kwh_per_km, has_gap, <signal>_mean (ambient_c, heater_kw, ac_kw …), split`
(+ BMW: `season, route, battery_temp_c_mean`; eVED: `veh_id, engine_type, speed_limit_kmh_mean,
intersection_sum, bus_stop_sum, engine_on_sum, electric_only`).

## Cleaning rules

- **Energy = battery V × I** (`battery_kw` > 0 = discharging). Not SoC (SoC has gaps and 0.1 % steps).
- BMW: columns found by name prefix (6 header versions). **Charging removed**: < 1 km/h with > 1 kW into the
  battery (B04, B09 fast charging). SoC ≤ 0 → missing (B14 glitch). Overview dates in two formats → both parsed;
  local Munich time → UTC.
- 10 Hz (BMW) / irregular (eVED) → **1 Hz** averages. Time gaps > 5 s are not counted as driving; segments with a
  gap are flagged `has_gap`.
- Elevation: BMW GPS altitude smoothed over 100 m; eVED uses its own `Elevation Smoothed`. Grade = Δh / distance
  over the same stretch.
- Segments ~200 m; last piece < 100 m dropped.
- eVED: only the 27 EV/PHEV vehicles; rows without battery V/I or speed dropped; |power| > 150 kW dropped;
  PHEV rows with engine running flagged (`electric_only`). Lat/lon removed from processed outputs.

## Time-based splits (golden rule 3)

- **BMW:** summer (A, Jun–Jul 2019) and winter (B, Dec 2019–Feb 2020) are split **separately by time**: earliest
  70 % of trips train, next 15 % val, last 15 % test – so both seasons appear in every split.
- **eVED:** trip start time, earliest 70 % train / 15 % val / 15 % test.
- Segments inherit the split of their trip (no segment of a test trip is ever in training).

## Known limits (state them in the thesis)

- Training data is **flat** (Munich, Ann Arbor: grade mostly within ±1.5 %). Hill effects must come from the physics
  part; Sri Lankan hill accuracy can only be shown with pilot trips.
- Only 2 real EV models (BMW i3, 2013 Nissan Leaf) + PHEVs in electric mode.
- Vehicle mass and CdA are **not** in the data → spec sheets (no invented values).
- eVED time zone assumed America/Detroit (not stated by the dataset).
- No Sri Lankan typical speeds → OSM road class / speed limits at route time.
