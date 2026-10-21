import shutil

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL, DB_DIR

DB_DIR.mkdir(parents=True, exist_ok=True)
# First start on a new computer: begin from the shared seed (vehicle models only, NO user data).
# c1.db itself (with real accounts) is never committed - see .gitignore.
if DATABASE_URL == f"sqlite:///{(DB_DIR / 'c1.db').as_posix()}" and not (DB_DIR / "c1.db").exists() \
        and (DB_DIR / "c1_seed.db").exists():
    shutil.copyfile(DB_DIR / "c1_seed.db", DB_DIR / "c1.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
