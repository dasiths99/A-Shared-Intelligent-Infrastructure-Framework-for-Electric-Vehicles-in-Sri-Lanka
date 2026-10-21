from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=6, max_length=100)
    district: str
    consent: bool

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("invalid email")
        return v.strip().lower()


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    token: str
    district: str


class VehicleModelOut(BaseModel):
    id: int
    make: str
    model: str
    variant: str | None
    year: int | None
    usable_kwh: float
    max_ac_kw: float | None
    max_dc_kw: float | None
    connector: str | None
    kwh_per_100km: float | None
    source: str
    model_config = {"from_attributes": True}


class VehicleModelIn(BaseModel):
    make: str
    model: str
    variant: str | None = None
    year: int | None = None
    usable_kwh: float = Field(gt=5, lt=250)
    max_ac_kw: float | None = None
    max_dc_kw: float | None = None
    connector: str | None = None
    kwh_per_100km: float | None = None
    source: str = Field(min_length=3, description="e.g. 'BYD Sri Lanka brochure 2026'")


class VehicleIn(BaseModel):
    model_id: int
    nickname: str | None = None
    battery_health_pct: float = Field(100, ge=50, le=100)
    home_charger_kw: float = Field(7.4, gt=1, le=22)
    tariff_type: str = "TOU"
    usual_plugin: str = "19:00"
    usual_departure: str = "07:30"
    min_soc_pct: float = Field(15, ge=5, le=50)
    let_app_schedule: bool = True


class VehicleOut(VehicleIn):
    id: int
    random_id: str
    model: VehicleModelOut | None = None
    model_config = {"from_attributes": True}


class PlanIn(BaseModel):
    vehicle_id: int
    soc_now_pct: float = Field(ge=0, le=100)
    soc_target_pct: float = Field(ge=10, le=100)
    plug_in_local: str | None = Field(None, description="HH:MM today; default = now")
    departure_local: str | None = Field(None, description="HH:MM next occurrence; default = usual departure")


class SessionOut(BaseModel):
    id: int
    vehicle_random_id: str
    plug_in_utc: datetime
    departure_utc: datetime
    soc_start_pct: float
    soc_target_pct: float
    kwh_needed: float
    planned_start_utc: datetime | None
    planned_end_utc: datetime | None
    cost_lkr: float
    uncontrolled_cost_lkr: float
    status: str
    model_config = {"from_attributes": True}
