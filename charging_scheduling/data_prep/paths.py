"""Folder locations for C1 data. Raw files are read-only inputs."""

from pathlib import Path

C1_ROOT = Path(__file__).resolve().parent.parent
RAW = C1_ROOT / "data" / "raw"
INTERIM = C1_ROOT / "data" / "interim"
PROCESSED = C1_ROOT / "data" / "processed"
RESULTS = C1_ROOT / "results"
