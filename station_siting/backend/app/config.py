"""C2 backend settings. C2_DATABASE_URL switches SQLite -> PostgreSQL/PostGIS without code changes."""

import os
from pathlib import Path

C2_ROOT = Path(__file__).resolve().parents[2]
DB_DIR = C2_ROOT / "database"
DATABASE_URL = os.environ.get("C2_DATABASE_URL", f"sqlite:///{(DB_DIR / 'c2.db').as_posix()}")
CORS_ORIGINS = ["http://localhost:5182", "http://127.0.0.1:5182"]
DEFAULTS = {"n_sites": 15, "radius_m": 3000, "station_mw": 0.5, "ev_share": 0.20, "power_factor": 0.9,
            "demand_mode": "temporal", "grid_constraint": True}
