# shared – used by C1, C2 and C3

Only things that **two or more** components need live here. Each component keeps its own code and data in its own folder.

| Path | Contents | Used by |
| --- | --- | --- |
| `config.py` | SEED, tariff, time periods, CRS, slot length, battery reserve | all |
| `vehicles/vehicle_list.csv` | Shared vehicle list (to be agreed) | C1, C3 |
| `db/schema.sql` | Shared database schema (to be agreed) | all |
| `data/raw/osm/` | OpenStreetMap Sri Lanka `.pbf` (ODbL) ✅ | C2, C3 |
| `data/raw/vehicles/` | Open EV Data JSON (2020, 118 models, no BYD) ✅ | C1, C3 |
| `data/raw/documents/` | PUCSL tariff Oct 2025, generation report, 2012 demand curve, DMT registrations ✅ | C1, C2 |
| `data/raw/boundaries/` | HDX admin boundaries: `lka_admin_boundaries.shp.zip` (polygons adm0–adm4, 118 MB) ✅ + `.xlsx` tables | C2 |
| `data/raw/chargers/` | `osm_charging_stations_LK_2026-10-19.json` – 66 OSM sites (41 without operator, 11 with socket info) ⚠️ **incomplete** (Volt Charge ~100 sites, ChargeNET 300+). Still needed: OCM (free key) + operator apps (Volt Charge, ChargeNET, ChargeUP/LIOC, Synogen) | C2, C3 |
