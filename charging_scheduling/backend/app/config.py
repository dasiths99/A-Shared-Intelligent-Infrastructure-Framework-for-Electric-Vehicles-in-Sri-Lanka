"""C1 backend settings. DATABASE_URL switches SQLite -> PostgreSQL without code changes."""

import os
from pathlib import Path

C1_ROOT = Path(__file__).resolve().parents[2]
PROJECT = C1_ROOT.parent
PROCESSED = C1_ROOT / "data" / "processed"
RESULTS = C1_ROOT / "results"
DB_DIR = C1_ROOT / "database"

DATABASE_URL = os.environ.get("C1_DATABASE_URL", f"sqlite:///{(DB_DIR / 'c1.db').as_posix()}")
TZ = "Asia/Colombo"
N_HOMES_FEEDER = 1000  # homes behind one feeder - used to weigh other drivers' planned EV load
DISTRICTS = ["Ampara", "Anuradhapura", "Badulla", "Batticaloa", "Colombo", "Galle", "Gampaha", "Hambantota",
             "Jaffna", "Kalutara", "Kandy", "Kegalle", "Kilinochchi", "Kurunegala", "Mannar", "Matale", "Matara",
             "Monaragala", "Mullaitivu", "Nuwara Eliya", "Polonnaruwa", "Puttalam", "Ratnapura", "Trincomalee",
             "Vavuniya"]
CORS_ORIGINS = ["http://localhost:5181", "http://127.0.0.1:5181"]
