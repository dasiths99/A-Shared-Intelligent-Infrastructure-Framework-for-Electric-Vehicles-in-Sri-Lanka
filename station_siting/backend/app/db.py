from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


class OptimizationRun(Base):
    """One planner run: parameters, metrics and the chosen sites (JSON)."""
    __tablename__ = "optimization_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    label: Mapped[str] = mapped_column(String(120))
    params_json: Mapped[str] = mapped_column(Text)
    metrics_json: Mapped[str] = mapped_column(Text)
    sites_json: Mapped[str] = mapped_column(Text)
    n_sites: Mapped[int] = mapped_column(Integer)
    coverage_pct: Mapped[float] = mapped_column(Float)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
