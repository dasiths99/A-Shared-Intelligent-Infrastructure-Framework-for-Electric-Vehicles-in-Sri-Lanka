# C2 data preparation – cleaned layers for station siting

**Raw data is never changed.** Code only reads `station_siting/data/raw/` and `shared/data/raw/`;
everything cleaned is written to `station_siting/data/processed/` (C2 only – no other component
reads it until the team decides to merge).

```
python -m station_siting.data_prep.run_all      # ~ a few minutes (OSM pass is the slow part)
python -m pytest station_siting/tests           # tests for parsers and cleaning rules
```

Needs the geo libraries in `station_siting/requirements.txt`. Report: `results/data_prep_report.json`.

## Output files (`data/processed/`, all WGS84 / EPSG:4326)

| File | Contents | Used for |
| --- | --- | --- |
| `district.parquet` | Colombo District polygon + area (km², EPSG:5235) | study area, H3 grid |
| `district_buffer.parquet` | district + 5 km | clip layers so edge hexagons see neighbours |
| `ds_divisions.parquet`, `gn_divisions.parquet` | 13 DS / GN divisions inside the district | results by area, joining statistics |
| `osm_roads.parquet` | roads motorway → residential: class, name, ref, maxspeed (km/h), lanes, oneway, length_m, `in_district` | road access criterion, traffic proxy (no RDA counts) |
| `osm_pois.parquet` | POIs with `category` and `role` (`candidate` = possible host site, `attractor` = demand, `existing` = charger), name, operator, `site_area_m2` | candidate sites, temporal demand index |
| `osm_landuse.parquet` | landuse polygons (residential, commercial, industrial, …) + area | land-suitability criterion |
| `worldpop_2020_colombo.tif` | population per ~100 m cell, clipped | demand index |
| `worldcover_2021_colombo.tif` | 10 m land cover, clipped | land-suitability criterion |
| `substations_osm.parquet` | OSM substations: name, voltage_kv_max, type, `is_grid_substation`, `in_district` | grid-distance criterion |
| `ceb_gss_capacity_2013plan.parquet` | 95 CEB grid substations: capacity 2025 (MVA), night/day peak 2012/2020/2025 (MW, MVA), spare MVA, utilisation, location + `location_source`, `serves_study_area` | **MCLP grid-capacity constraint** |
| `existing_chargers_osm.parquet` | OSM chargers: operator, sockets, max kW, is_dc, `in_district` | distance-to-existing criterion, hold-out validation |
| `dmt_new_registrations_2019_2023.csv` | new vehicles by class × fuel, 2019–2023 (national) | EV growth scenarios |

## Rules and choices

- **POI categories** – candidates: fuel station, supermarket, mall, car park, hotel, rest area.
  Attractors: office, education, health, food, bank, worship, market, entertainment, transport hub, sports.
- POIs mapped as areas → centroid (+ `site_area_m2`). Same category within 30 m → one site (dedupe).
- Roads: OSM `_link` roads grouped into their parent class (`road_class`); zero-length pieces dropped.
- Broken OSM geometries (missing nodes, invalid rings) are skipped.
- **Substation capacity:** CEB *Long Term Transmission Development Plan 2013–2022*, Tables 3.1 (night peak)
  and 3.2 (day peak). `capacity_2025_mva` = installed MVA after planned expansions up to 2025.
  `peak_2025_mva` = √(MW² + MVAr²), larger of night/day. `spare_2025_mva` = capacity − peak.
  Locations: exact/fuzzy name match to OSM substations; else OSM place name (approximate, flagged).

## Known limits (state them in the thesis)

- **Substation numbers are a 2013 forecast for 2025, not measured loading** → treat as an assumption,
  run ±20 % sensitivity; replace when CEB data arrives via the supervisor.
- Existing chargers from OSM are **incomplete** → collect operator lists for hold-out validation.
- No RDA traffic counts → road class / speed used as traffic proxy.
- DMT registrations are national only and stop at 2023.
- WorldCover counts home gardens as "tree" → built-up share is low for Colombo.
- Expressway corridor not chosen yet → only Colombo District for now.
