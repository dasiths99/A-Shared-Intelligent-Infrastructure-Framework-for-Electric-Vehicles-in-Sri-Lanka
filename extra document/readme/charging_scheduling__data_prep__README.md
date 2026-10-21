# C1 data preparation – cleaned, training-ready data

**Raw data is never changed.** Code only reads `data/raw/`; cleaned files are written to
`data/interim/` and `data/processed/` (Parquet). Re-run any time:

```
python -m charging_scheduling.data_prep.run_all              # everything (~RECON step is slow)
python -m charging_scheduling.data_prep.run_all --skip-recon # sessions + monthly + UrbanEV only
python -m pytest charging_scheduling/tests                   # tests for every cleaning rule
```

Row counts removed by each rule are written to `results/data_prep_report.json`.

## Output files

| File | One row = | Use for (model) |
| --- | --- | --- |
| `processed/ev_sessions_clean.parquet` | one charging session (ACN + Utrecht + Boulder) | 1.2 routine clustering, 1.3 need prediction, EV demand for 1.1, simulator 1.5 |
| `processed/ev_users_summary.parquet` | one driver (ACN, Utrecht; shared IDs removed) | pick users with ≥ 10 sessions (cold-start rule) |
| `processed/recon_baseload_15min.parquet` | one 15-min slot: average Sri Lankan household load | 1.1 base-load forecast, 1.4 scheduler base load `L_t` |
| `interim/recon_household_15min.parquet` | one household × one 15-min interval (kWh) | household-level analysis, other aggregations |
| `processed/recon_monthly_clean.parquet` | one household × one month (kWh) | household size / segment checks |
| `processed/urbanev_zone_hourly.parquet` | one Shenzhen zone × one hour | station busyness forecast |
| `processed/urbanev_zone_info.parquet` | one zone | zone location, size, number of piles |

## `ev_sessions_clean` columns

| Column | Meaning |
| --- | --- |
| `source` | `acn`, `utrecht`, `boulder` |
| `site` | `caltech`, `jpl`, `office001`, `asr_utrecht`, `boulder` |
| `session_id`, `station_id` | ids from the source |
| `user_id` | pseudonymous driver id with source prefix (`acn_…`, `utr_…`); empty for Boulder |
| `arrival_utc`, `departure_utc` | plug-in / unplug time, **UTC** |
| `done_charging_utc`, `charging_h` | when charging finished (ACN) / hours charging (ACN, Boulder) |
| `kwh` | energy delivered |
| `stay_h` | hours plugged in |
| `tz` | local time zone of the site |
| `arrival_hour_local`, `departure_hour_local`, `weekday`, `is_weekend`, `arrival_date_local` | local-clock features |
| `kwh_requested`, `requested_departure_utc`, `minutes_available`, `miles_requested`, `wh_per_mile`, `n_user_inputs`, `user_input_utc` | ACN driver's **first** app input (what the scheduler would know at plug-in) |
| `rail`, `battery_kwh_survey` | Utrecht only |
| `port_type` | Boulder only (all Level 2) |
| `flag_shared_id` | Utrecht ID used by several people → do **not** use for personal routines |
| `flag_controlled_charging` | Utrecht deck sessions under smart charging (from Mar 2023) → energy is not "natural" |
| `flag_covid_period` | ACN sessions from Mar 2020 (behaviour changed) |
| `split` | `train` / `val` / `test` / `excluded` – **time-based** (see below) |

## Cleaning rules (sessions)

1. Missing or impossible times (incl. DST-ambiguous local times) → removed.
2. Duplicates: same session id; same station + start + end; same station + start minute + kWh
   (Boulder file contains ~62 k exact duplicates and Jun–Aug 2023 twice in two date formats).
3. Stay < 5 min or > 48 h → removed.
4. kWh ≤ 0, > 100 kWh, or average power (kWh / stay) > 50 kW → removed.
5. Charging time < 0 or longer than the stay → set to missing (session kept).

## Cleaning rules (RECON-SL 15-min)

- Meter values are **cumulative**: energy per interval = difference of two readings of the same
  meter exactly 15 min apart. Gaps (≠ 15 min) are left missing – never guessed.
- Negative differences (meter reset / replacement) and > 3.75 kWh per 15 min (> 15 kW) removed.
- Local time Asia/Colombo (UTC+05:30) → UTC. Reading at t covers (t − 15 min, t].
- Base load: average over households per slot; slots with < 50 reporting households dropped.

## Time-based splits (golden rule 3)

| Data | train | val | test | excluded |
| --- | --- | --- | --- | --- |
| ACN | 2018-04 → 2019-07 | 2019-08 → 2019-10 | 2019-11 → 2020-02 | from 2020-03 (COVID) |
| Utrecht | 2020-08 → 2024-01 | 2024-02 → 2024-05-21 | 2024-05-22 → 2024-10 | – |
| Boulder | 2018-01 → 2023-04-10 | 2023-04-11 → 2023-07-28 | 2023-07-29 → 2023-11 | – |
| RECON base load | 2023-10 → 2024-07 | 2024-08 → 2024-10-15 | 2024-10-16 → 2024-12-23 | – |
| UrbanEV | 2022-09 → 2022-12 | 2023-01 | 2023-02 | – |

Dates are in `run_all.py` (`SESSION_SPLITS`, `BASELOAD_SPLIT`, `URBANEV_SPLIT`) and in the report.

## Known limits (state them in the thesis)

- EV sessions are from the USA and the Netherlands, not Sri Lanka (Sri Lankan pilot data comes later).
- ACN user inputs: 52 % (Caltech), 94 % (JPL), 35 % (office001) of sessions have them.
- Utrecht battery size only for ~7 % of sessions (survey).
- UrbanEV zip has no weather file; `occupancy` looks like a count of busy piles, not % – check.
- RECON-SL data dictionary not included in the download.
