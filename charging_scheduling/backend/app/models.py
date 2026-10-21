"""C1 database tables - privacy-separated (CLAUDE.md golden rule 1).

users             login data ONLY (email, password hash, district, consent). Never read by ML.
vehicle_models    shared vehicle list (make, model, battery, charging power, connector).
vehicles          one owner's EV + preferences. Linked to the user, has a pseudonymous random_id.
charging_sessions plans/sessions keyed ONLY by vehicle random_id + district (no user id, no name, no GPS).
                  This is the only table models read.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

now = lambda: datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    district: Mapped[str] = mapped_column(String(40))
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    token: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class VehicleModel(Base):
    __tablename__ = "vehicle_models"
    id: Mapped[int] = mapped_column(primary_key=True)
    make: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(80))
    variant: Mapped[str | None] = mapped_column(String(80), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usable_kwh: Mapped[float] = mapped_column(Float)
    max_ac_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_dc_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    connector: Mapped[str | None] = mapped_column(String(60), nullable=True)
    kwh_per_100km: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(120), default="Open EV Data (2020)")


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    random_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("vehicle_models.id"))
    nickname: Mapped[str | None] = mapped_column(String(40), nullable=True)
    battery_health_pct: Mapped[float] = mapped_column(Float, default=100)
    home_charger_kw: Mapped[float] = mapped_column(Float, default=7.4)
    tariff_type: Mapped[str] = mapped_column(String(10), default="TOU")  # TOU / normal
    usual_plugin: Mapped[str] = mapped_column(String(5), default="19:00")
    usual_departure: Mapped[str] = mapped_column(String(5), default="07:30")
    min_soc_pct: Mapped[float] = mapped_column(Float, default=15)
    let_app_schedule: Mapped[bool] = mapped_column(Boolean, default=True)
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ChargingSession(Base):
    __tablename__ = "charging_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_random_id: Mapped[str] = mapped_column(String(36), index=True)  # pseudonymous only
    district: Mapped[str] = mapped_column(String(40))
    plug_in_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    departure_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    soc_start_pct: Mapped[float] = mapped_column(Float)
    soc_target_pct: Mapped[float] = mapped_column(Float)
    kwh_needed: Mapped[float] = mapped_column(Float)
    planned_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_kw_json: Mapped[str] = mapped_column(Text)  # 15-min power plan (kW) from plug-in
    cost_lkr: Mapped[float] = mapped_column(Float)
    uncontrolled_cost_lkr: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), default="planned")
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
