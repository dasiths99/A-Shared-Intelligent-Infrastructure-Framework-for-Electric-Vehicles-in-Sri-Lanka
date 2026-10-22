"""C3 backend core: settings, database (SQLite -> PostgreSQL via C3_DATABASE_URL), cached graph / models."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd
import xgboost as xgb
from sqlalchemy import DateTime, Float, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from route_recommendation.routing.graph import RoadGraph

C3 = Path(__file__).resolve().parents[2]
PROJECT = C3.parent
PROCESSED = C3 / "data" / "processed"
RESULTS = C3 / "results"
DATABASE_URL = os.environ.get("C3_DATABASE_URL", f"sqlite:///{(C3 / 'database' / 'c3.db').as_posix()}")
CORS_ORIGINS = ["http://localhost:5183", "http://127.0.0.1:5183"]

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


class TripLog(Base):
    """Every route request (no personal data: only town-level origin/destination names and results)."""
    __tablename__ = "trip_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    origin: Mapped[str] = mapped_column(String(120))
    destination: Mapped[str] = mapped_column(String(120))
    vehicle_id: Mapped[int]
    start_soc_pct: Mapped[float] = mapped_column(Float)
    result_json: Mapped[str] = mapped_column(Text)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _read(table: str) -> pd.DataFrame:
    try:
        return pd.read_sql(f"SELECT * FROM {table}", engine)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("C3 database not seeded - run: python -m route_recommendation.database.seed") from e


@lru_cache
def graph() -> RoadGraph:
    return RoadGraph(PROCESSED)


@lru_cache
def vehicles() -> pd.DataFrame:
    return _read("vehicles")


def vehicles_reload() -> None:
    vehicles.cache_clear()


@lru_cache
def chargers() -> pd.DataFrame:
    return _read("chargers")


@lru_cache
def places() -> pd.DataFrame:
    return _read("places")


@lru_cache
def hybrid(model_file: str | None):
    if not model_file or not (RESULTS / model_file).exists():
        return None
    m = xgb.XGBRegressor()
    m.load_model(RESULTS / model_file)
    return m


@lru_cache
def weather_means() -> pd.DataFrame:
    w = pd.read_parquet(PROCESSED / "weather_hourly.parquet")
    return w.groupby("town").agg(temp_c=("temp_c", "mean"), lat=("lat", "first"), lon=("lon", "first")).reset_index()


@lru_cache
def const_kwh_per_km() -> dict[str, float]:
    """Manufacturer-average consumption from Open EV Data (constant kWh/km baseline)."""
    raw = PROJECT / "shared/data/raw/vehicles/open_ev_data.json"
    if not raw.exists():  # raw data is not in git - fresh clones use the cleaned copy
        s = pd.read_parquet(PROCESSED / "vehicle_specs_openev.parquet").dropna(subset=["kwh_per_100km", "usable_kwh"])
        return {f"{r.brand} {r.model}|{float(r.usable_kwh)}": r.kwh_per_100km / 100 for r in s.itertuples()}
    d = json.loads(raw.read_text(encoding="utf-8"))["data"]
    out = {}
    for v in d:
        c = (v.get("energy_consumption") or {}).get("average_consumption")
        if c and v.get("usable_battery_size"):
            out[f"{v['brand']} {v['model']}|{v['usable_battery_size']}"] = c / 100
    return out
