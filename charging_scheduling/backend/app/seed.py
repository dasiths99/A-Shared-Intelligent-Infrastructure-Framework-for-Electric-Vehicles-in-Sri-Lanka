"""Fill vehicle_models from Open EV Data (shared raw file) on first start. BYD etc. are added via the API
with their brochure as `source` (no invented specs)."""

import json

from .config import PROJECT
from .db import SessionLocal
from .models import VehicleModel

OPEN_EV = PROJECT / "shared" / "data" / "raw" / "vehicles" / "open_ev_data.json"


def seed_vehicle_models() -> int:
    db = SessionLocal()
    try:
        if db.query(VehicleModel).count() > 0 or not OPEN_EV.exists():
            return 0
        seen = set()
        for v in json.loads(OPEN_EV.read_text(encoding="utf-8"))["data"]:
            if v.get("type") != "bev" or not v.get("usable_battery_size"):
                continue
            ac, dc = v.get("ac_charger") or {}, v.get("dc_charger") or {}
            key = (v["brand"], v["model"], v.get("variant") or "", v.get("release_year"), v["usable_battery_size"])
            if key in seen:
                continue
            seen.add(key)
            ports = (dc.get("ports") or []) + [p for p in (ac.get("ports") or []) if p not in (dc.get("ports") or [])]
            db.add(VehicleModel(make=v["brand"], model=v["model"], variant=v.get("variant") or None,
                                year=v.get("release_year"), usable_kwh=v["usable_battery_size"],
                                max_ac_kw=ac.get("max_power"), max_dc_kw=dc.get("max_power"),
                                connector=";".join(ports) or None,
                                kwh_per_100km=(v.get("energy_consumption") or {}).get("average_consumption"),
                                source="Open EV Data (2020)"))
        db.commit()
        return len(seen)
    finally:
        db.close()
