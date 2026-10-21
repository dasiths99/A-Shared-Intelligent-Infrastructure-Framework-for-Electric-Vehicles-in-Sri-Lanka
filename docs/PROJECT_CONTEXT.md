# Project Context – J26-IT-430

**Title:** A Shared Intelligent Infrastructure Framework for Electric Vehicles in Sri Lanka
**Module:** SLIIT IT4010 Research Project, 2026 July intake · **Group:** CoEAI (Centre of Excellence for AI) · **Specialization:** IT
**Topic Assessment Form (TAF):** approved; supervisors ticked Yes on scope, novelty, ability, specialization fit, data availability.
**Timeline:** July 2026 – June 2027 (integration of components: March–April 2027).

## Related documents (Claude Docs, private links)

- Component 1 proposal: https://claude.ai/code/artifact/1d41781c-4d86-42e4-ae7e-cac5c751a743
- Component 2 proposal: https://claude.ai/code/artifact/b3ae7ed7-996a-42ca-a744-dd75262a4d07
- Component 3 proposal: https://claude.ai/code/artifact/f94840fe-393b-489f-af3e-20d34ad24c47
- Project Guide (simple explanation, datasets, models): https://claude.ai/code/artifact/1162143c-775f-4438-9b2a-dc53732ea26f
- Original files: TAF `IT4010-EV-430-TAF-2026 Jan V2_2 new.pdf`; original C2 and C3 individual proposals.

## 1. The problem

1. Most EV owners charge at home in the evening, the national peak (18:30–22:30). Even "charge after 22:30" can create a new **rebound peak** when everyone starts together.
2. Charging stations are built where demand is low, or where the substation has little spare capacity.
3. Navigation apps do not predict whether an EV battery is enough for a trip, especially in the hill country (Colombo → Nuwara Eliya climbs about 1,900 m).

SDGs: 7 (Clean Energy), 9 (Industry, Innovation, Infrastructure), 13 (Climate Action).

## 2. How the components connect

```
Public datasets   Owner app + survey   Shared vehicle list
        \                 |                 /
         Shared database + API (random IDs, district level only)
        /                 |                 \
   C1 When ──growth forecast──▶ C2 Where ──planned sites──▶ C3 Which route
     │                         ◀──trips needing a stop──        ▲
     └──────────── station busyness forecast ──────────────────┘
```

Story: Kamal registers his EV. C1 tells him to charge 00:10–02:40 so he is ready by 07:15 without adding to the peak. On Saturday he drives to Nuwara Eliya; C3 says one stop is needed at Kegalle, which C1 forecasts will be quiet then. That charger exists because C2 showed the area needed one.

## 3. Component 1 – Personalized, Routine-Aware EV Charging Scheduling

**Owner:** Pitadeniya A P I U (IT23310650)

**Pipeline**
1. App registration: account (email/phone, district, consent), vehicle profile (make/model from list → usable kWh, AC/DC kW, connector, kWh/100 km auto-filled; year; battery health optional), preferences (home charger + kW, tariff type normal/TOU, usual plug-in & departure, minimum SoC, "let app schedule" flag). Multiple vehicles per account.
2. Per session input: current SoC, target SoC, departure time (pre-filled from routine; user taps Confirm).
3. Routine learning: per weekday typical plug-in, departure, kWh, plug-in SoC; K-Means routine types (office commuter, shift worker, weekend user, high-use taxi/three-wheeler).
4. Need prediction: XGBoost / Random Forest; quantile regression for safe early departure (e.g. 10th percentile). Cold start: profile defaults + routine-type average until ~10 sessions.
5. Demand forecast: base grid load + aggregate EV demand, 24 h ahead, 15-min slots (LSTM / GRU / XGBoost vs seasonal-naive).
6. Coordinated scheduler: LP / QP, rolling 24 h horizon re-solved every 15 min (MPC).
   - Objective: minimize Σ_t (L_t + Σ_i p_{i,t})²  (or linearized peak); cost-aware variant adds TOU price.
   - Constraints: charge only between plug-in and predicted departure; 0 ≤ p ≤ min(vehicle, charger kW); energy ≥ need; SoC ≥ minimum reserve.
7. Output: "Charge 00:10–02:40, 80 % by 07:15, save LKR 120".

**Research questions:** RQ1 coordinated scheduler vs uncontrolled / fixed TOU / TOU+random delay. RQ2 personalized predictions vs defaults.
**Metrics:** peak reduction %, peak-to-average ratio, car-ready rate (≥ 95 %), departure MAE (min), energy MAE (kWh), forecast MAE/RMSE/MAPE, owner cost LKR, scheduler run time (< 60 s for 10k EVs, to confirm), acceptance %, SUS ≥ 68.
**Scenarios:** 10k / 50k / 100k EVs; compliance 50 / 80 / 100 %.
**Data layer:** pluggable EV Data Interface – simulator now; telematics APIs, OBD-II, OCPP later (no manufacturer access now).
**Database (privacy-separated):** USERS (login) · VEHICLES · VEHICLE_MODELS · CHARGING_SESSIONS (random_id only). ML reads only CHARGING_SESSIONS.

## 4. Component 2 – Grid-Aware Temporal Multi-Criteria Optimization of EV Charging Station Locations

**Owner:** Senanayake S G (IT23289352)

**Pipeline**
1. H3 hexagon grid over Colombo District + one expressway corridor (~0.7 km² cells urban).
2. Temporal demand per hexagon for 4 periods (weekday/weekend × peak/off-peak) × 2–3 growth scenarios (C1 growth factors). Inputs: road class + RDA counts (if available), POIs weighted by period, WorldPop, district EV share (DMT + survey), share without home charging (survey).
3. Hotspots: K-Means (elbow + Silhouette) and DBSCAN (k-distance); keep the better by Silhouette / Davies-Bouldin.
4. Real buildable candidate sites from OSM: fuel stations, malls, supermarkets, car parks, hotels, expressway rest areas.
5. AHP-weighted MCDM (consistency ratio < 0.1): demand, road access, grid capacity (distance + estimated spare capacity), land suitability (WorldCover + OSM landuse), distance to existing chargers.
6. MCLP: max Σ D_h y_h s.t. y_h ≤ Σ_{j∈N_h} x_j, Σ x_j = N, Σ_{j∈S_s} P x_j ≤ C_s, binary. Service distance 3 km urban / 25 km expressway; PuLP + CBC.
7. Interactive web map (Leaflet / Kepler.gl) with scores and reasons; export CSV/GeoJSON.

**RQ:** does time-based demand + real candidates + grid-constrained MCLP cover more demand and stay more stable than traffic-only, clustering-only, static MCDM and no-grid-constraint?
**Metrics:** demand coverage %, hold-out hit rate (existing stations hidden), ranking stability (top-10 overlap ≥ 70 %, Kendall τ under ±20 % weights), grid violations = 0, Silhouette/DBI, AHP CR < 0.1, run time, SUS ≥ 68.

## 5. Component 3 – Terrain- and SoC-Aware EV Route and Charging-Stop Recommendation (Hybrid Physics–ML)

**Owner:** Seniya K A D D (IT23273658)

**Pipeline**
1. Input: start, destination, current SoC, vehicle from shared profile.
2. OSRM on Sri Lanka OSM → 3–5 alternative routes.
3. ~200 m segments with smoothed elevation (Copernicus DEM / SRTM), road class, typical speed by time of day.
4. Energy per segment: physics P = (m·a + m·g·Cr·cosθ + ½·ρ·CdA·v² + m·g·sinθ)·v; battery energy = P·Δt/η_drive when P > 0, P·Δt·η_regen when P < 0 (Fiori et al. 2016). Plus XGBoost residual on speed variability, stop density, road class, time, temperature.
5. SoC tracking vs reserve (15 %).
6. Charging stop for infeasible routes: detour, charger kW, connector match, C1 forecast busyness.
7. Rank by energy, total time (drive + charge), arrival SoC; show energy per section ("climb costs 3.2 kWh").

**RQ1:** hybrid more accurate than constant kWh/km, physics-only, ML-only (esp. hilly)? **RQ2:** recommended routes reach destination ≥ reserve more often than shortest/fastest?
**Metrics:** energy MAE kWh / MAPE on held-out real trips, hilly vs flat error, feasibility rate, energy saving via independent physics reference, detour min, response < 3 s, Likert + SUS.
**Test routes:** Colombo–Kandy, Colombo–Nuwara Eliya, Colombo–Galle (expressway), Colombo–Jaffna. ABRP used only as qualitative sanity check.

## 6. Shared data collection (one consent form, one ethics application)

| Method | Size | Collects | Used by |
| --- | --- | --- | --- |
| Online owner survey (~10 min) | 50–150 owners | district, vehicle, home charger, tariff, usual times, public chargers used, wanted charger locations, long trips, range anxiety, nav app | C1, C2, C3 |
| App pilot (3–4 weeks) | 10–20 owners | sessions (SoC, times, kWh); trips (start/end area, distance, start/end SoC) | C1, C3 |
| Expert interviews (optional) | 2–3 | AHP weights, grid assumptions | C2, C1 |

Rules: random IDs, district/area level, no plates/VIN/NIC/address/continuous GPS, right to delete, PDPA No. 9 of 2022 principles. No survey/pilot before SLIIT ethics approval. Own data is for calibration and testing, not training big models.

## 7. Models to build (14)

| # | Model | Type | Tools | Baseline |
| --- | --- | --- | --- | --- |
| 1.1 | Grid + EV demand forecast | LSTM/GRU/XGBoost | Keras, XGBoost | same time last week |
| 1.2 | Routine clustering | K-Means | scikit-learn | – |
| 1.3 | Need prediction | XGBoost/RF + quantile | XGBoost | profile defaults |
| 1.4 | Coordinated scheduler | LP/QP, rolling horizon | PuLP / CVXPY | uncontrolled, TOU, TOU+random |
| 1.5 | EV data simulator | Monte Carlo | NumPy | – |
| 2.1 | Temporal demand index | weighted score per hexagon | GeoPandas, h3 | traffic only |
| 2.2 | Hotspots | K-Means + DBSCAN | scikit-learn | K-Means centres |
| 2.3 | Criteria weights | AHP | NumPy | equal weights |
| 2.4 | Site scoring | weighted sum / TOPSIS | Python, PostGIS | static MCDM |
| 2.5 | Site selection | MCLP (binary IP) | PuLP CBC | no grid constraint |
| 3.1 | Physics energy | vehicle dynamics | NumPy | constant kWh/km |
| 3.2 | ML residual | XGBoost | XGBoost | physics-only, ML-only |
| 3.3 | Routes + SoC tracking | OSRM + calc | OSRM, rasterio | shortest, fastest |
| 3.4 | Charging-stop selection | rule scoring / constrained search | Python | nearest charger |

## 8. Tech stack

Python 3.11, pandas, NumPy, scikit-learn, XGBoost, TensorFlow/Keras, PuLP/CVXPY, GeoPandas, h3, rasterio, PostgreSQL + PostGIS, OSRM (Docker), FastAPI, Flutter or React Native, Leaflet/Kepler.gl, Git.

## 9. Budget (harmonized)

Each component: human effort LKR 100,000 (opportunity cost); direct costs C1 ≈ 57,500, C2 ≈ 42,000, C3 ≈ 42,000.

## 10. Open items (before proposal submission)

- Confirm supervisor and co-supervisor names/spelling.
- Verify every reference against the original paper.
- Choose the expressway corridor (C2) with the supervisor.
- Redraw figures in draw.io if the brief requires black-and-white, non-AI diagrams.
- Agree shared survey, consent form and ethics application.
- Complete AI-use disclosures and decision logs after real supervisor meetings.
