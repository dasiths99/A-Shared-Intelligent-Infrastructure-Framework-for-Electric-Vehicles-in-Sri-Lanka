# Datasets – J26-IT-430 (verified online 17 Oct 2026)

Raw files live inside each component's own folder, exactly as `scripts/download_datasets.py` creates them
(layout changed 18 Oct 2026). Short paths in the tables below map to:

| Table path | Real folder |
| --- | --- |
| `data/raw/C1_charging_scheduling/…`, `…/` (C1 table) | `charging_scheduling/data/raw/…` |
| `C2/…` | `station_siting/data/raw/…` |
| `C3/…` | `route_recommendation/data/raw/…` (BMW i3 = `route_recommendation/data/raw/bmw_i3_tum/`) |
| `shared/…` (osm, vehicles, documents, boundaries, chargers) | `shared/data/raw/…` |

See the component READMEs in `extra document/readme/` for the current download status.

## Key findings

- **VED has only 3 pure EVs + 24 PHEVs** (383 vehicles total) → C3 also uses the **BMW i3 TUM** dataset.
- **RECON-SL** gives real Sri Lankan 15-min household load (1,438 homes) → C1 home base-load shape.
- **Tariff changed 15 Oct 2025** (see `extra document/claude/CLAUDE.md` §4).
- **Open Charge Map Sri Lanka data is outdated** (2023 editor note); Volt Charge alone has 100+ sites → build own charger list.
- **Not openly published:** RDA traffic counts, CEB substation capacity, operator charger lists → request via supervisor.

## C1 – Charging scheduling

| Dataset | Contents | Access | Path | Licence |
| --- | --- | --- | --- | --- |
| ACN-Data (Caltech) https://ev.caltech.edu/dataset | Sessions at caltech (54 EVSE), jpl (50), office001 (8): connectionTime, disconnectTime, doneChargingTime, kWhDelivered, sessionID, siteID, spaceID, stationID, timezone, userID (app users), userInputs[WhPerMile, kWhRequested, milesRequested, minutesAvailable, modifiedAt, paymentRequired, requestedDeparture] | Free token; API or `acnportal` | `charging_scheduling/data/raw/acn_data/` ✅ 66,745 sessions (caltech 31,424 · jpl 33,638 · office001 1,683), Apr 2018 – Sep 2021, downloaded 19 Oct 2026 | check site terms |
| Utrecht office parking (4TU) https://doi.org/10.4121/80ef3824-3f5d-4e45-8794-3b8791efbd13.v1 | 55,000+ sessions, Aug 2020–Oct 2024, ~300 chargers; arrival, departure, energy, station, anonymised user | Free download | …/utrecht_4tu/ | CC BY-NC-SA 4.0 |
| ~~Palo Alto charging usage (ORNL hub)~~ | **Withdrawn** (ORNL export 0 records, city portal 404 – checked 19 Oct 2026) | – | – | – |
| City of Boulder EV charging (ArcGIS open data) – replaces Palo Alto | ~148k public sessions 2018+: station, address, start/end, duration, charging time, kWh, port type ✅ | Free | `charging_scheduling/data/raw/boulder/` | city open data terms – check |
| UrbanEV Shenzhen (Dryad, version 2026-02-04) | Station-raw 5-min for 1,682 stations (busy/idle, fast/slow, prices, kWh) + 22,650 piles (kW, AC/DC) + coordinates; zone-cleaned 5-min & 1-hour for 275 zones + adjacency/distance + weather; Sep 2022–Feb 2023 ✅ (manual browser download – Dryad API needs login) | Free (login) | `charging_scheduling/data/raw/urbanev/` | Dryad = CC0 (check README) |
| RECON-SL (IEEE DataPort) | 4,063 households monthly bills (20 months); smart meter 15-min `smart_15min_1..3.csv` (2023-10-01 → 2024-12-23, ~45.6 M rows, **cumulative** import/export kWh + V, A, PF) and 6-hour `smart_6hour_1..5.csv` (2023); survey waves 1–3 (appliances, behaviour, TOU awareness, billing). 5.3 GB unzipped. ✅ on disk 19 Oct 2026; `data_dictionary.csv` not included | Free IEEE login (manual) | `charging_scheduling/data/raw/recon_sl/` | see readme |
| PUCSL daily generation reports | Night/day peak, off-peak min (MW), generation by source, demand charts (values need digitizing) | Free PDFs | shared/documents/ | public |
| PUCSL 2012 demand curve study | Weekday & Sunday system load curves (14 days, Sep 2012) | Free PDF | shared/documents/ | public |
| PUCSL tariff table (Oct 2025) | TOU periods & rates, EV station rates | Free PDF | shared/documents/ | public |

## C2 – Station siting

| Dataset | Contents | Access | Path | Licence |
| --- | --- | --- | --- | --- |
| OpenStreetMap Sri Lanka (Geofabrik) | Roads, POIs (fuel, mall, supermarket, parking, hotel), power lines/substations; .pbf ~137 MB | Free | shared/osm/ | ODbL |
| WorldPop Sri Lanka 100 m | Population 2010/2012/2015/2020 GeoTIFF | Free | C2/worldpop/ | CC BY 4.0 |
| ESA WorldCover v200 | 2021, 10 m, 11 land-cover classes; tiles N03/N06/N09 × E078/E081 | Free | C2/worldcover/ | CC BY 4.0 |
| HDX admin boundaries (cod-ab-lka) | Admin levels to level 4; `lka_admin_boundaries.shp.zip` ✅ + XLSX | Free | shared/boundaries/ | CC BY-IGO |
| Statistical Abstract 2024 Table 7.3 (DMT) | New registrations by class & fuel (incl. electric), 2019–2023, national | Free PDF | shared/documents/ | public |
| Open Charge Map LK + operator lists | location, operator, connector, kW (e.g. chargeNET Beruwala Type 1 6.6 kW) | Free key | shared/chargers/ | OCM terms |
| OSM chargers (Overpass, 19 Oct 2026) | 66 `amenity=charging_station` sites – incomplete ⚠️ | Free | `shared/data/raw/chargers/` | ODbL |
| OSM substations + plants (Overpass, 19 Oct 2026) | 141 substations (~55 with voltage 33/132/220 kV), 221 plants; no MVA ✅ | Free | `station_siting/data/raw/osm_power/` | ODbL |
| CEB Long Term Transmission Development Plan 2013–2022 (PUCSL) | Old transmission plan PDF – fallback for grid substations (contents not yet checked) ⚠️ | Free PDF | `station_siting/data/raw/ceb/` | public |
| RDA traffic counts | traffic volumes – no open dataset found online (19 Oct 2026) | **request** | C2/rda/ | – |
| CEB substation capacity | MVA / loading (current) | **request** | C2/ceb/ | – |

## C3 – Route and charging stop

| Dataset | Contents | Access | Path | Licence |
| --- | --- | --- | --- | --- |
| VED https://github.com/gsoh/VED | 383 vehicles, Ann Arbor, Nov 2017–Nov 2018, 373,964 miles; EV signals: SoC, battery V & I, speed, GPS, OAT, heater power. Files: VED_DynamicData.7z (weekly CSV), VED_Static_Data_PHEV&EV.xlsx | Free (git) | C3/VED/ | Apache-2.0 |
| eVED (Bitbucket) | VED map-matched + elevation, speed limits, intersections, signals, stop signs | Free (git clone, large) | C3/eVED/ | Apache-2.0 (repo) |
| BMW i3 real driving cycles (TUM, IEEE DataPort) | 70 trip CSVs (A01–A32 summer, B01–B38 winter), 1,357 km, 10 Hz: speed, elevation, temperature, battery V/I/SoC, heating power ✅ | Free IEEE login (manual) | `route_recommendation/data/raw/bmw_i3_tum/` | see readme |
| BMW i3 TUM **simulation** data (same IEEE page) | 24 simulated runs: ambient −10/0/+10 °C × Standard/Heating/Charging/Mixed × CAN/LIN (`.csv` + `.mat`); slope, wind, traction force, Crr, mass, pack V/I, SoC, heater power. **Simulation only – not for accuracy evaluation** ✅ | Free IEEE login (manual) | `route_recommendation/data/raw/bmw_i3_tum_simulation/` | see readme |
| Copernicus DEM GLO-30 | 30 m surface model, 1°×1° tiles N05–N09 × E079–E081 | Free | C3/elevation_copernicus_dem/ | Copernicus licence |
| Open-Meteo archive | Hourly temperature & humidity 2023–2025 for 8 towns | Free, no key | C3/weather_open_meteo/ | CC BY 4.0 |
| Open EV Data | usable kWh, AC/DC kW, DC curve, connectors, consumption (no mass/drag) | Free (GitHub JSON) | shared/vehicles/ | see LICENSE |
| Manufacturer spec sheets | mass, CdA, Crr, efficiencies for 3–4 models | manual | shared/vehicles/vehicle_list.csv | – |

## Data the group must collect

- Sri Lankan EV sessions and trips → owner pilot (app).
- Current charger list → operator apps/websites (record date checked).
- Vehicle mass / drag area → spec sheets.
