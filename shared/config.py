"""Project-wide constants shared by C1, C2 and C3 (see CLAUDE.md section 4)."""

SEED = 42

# Coordinates: store WGS84, compute distances/areas in SLD99 (metres)
CRS_STORE = "EPSG:4326"
CRS_METRIC = "EPSG:5235"

# Time: store UTC, display Colombo time
TZ_DISPLAY = "Asia/Colombo"
SLOT_MINUTES = 15

PERIODS = ("weekday_peak", "weekday_offpeak", "weekend_peak", "weekend_offpeak")

BATTERY_RESERVE = 0.15

# PUCSL tariff effective 15 Oct 2025 (LKR/kWh) - re-check before final results
TOU_DOMESTIC = {
    "peak": {"start": "18:30", "end": "22:30", "lkr_per_kwh": 67},
    "day": {"start": "05:30", "end": "18:30", "lkr_per_kwh": 35},
    "offpeak": {"start": "22:30", "end": "05:30", "lkr_per_kwh": 21},
}
TOU_FIXED_LKR_PER_MONTH = 2100
EV_STATION_TARIFF = {  # LKR/kWh for peak / day / off-peak
    "dc": {"peak": 111, "day": 87, "offpeak": 53},
    "ac_l2": {"peak": 90, "day": 70, "offpeak": 40},
}
