"""Loads data and trained models once (lazy) for the C1 API."""

from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd
import xgboost as xgb

from charging_scheduling.forecasting import baseload

from .config import PROCESSED, RESULTS


def _latest(pattern: str):
    files = sorted(RESULTS.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in results/ - run notebooks/c1_model_training.ipynb first")
    return files[-1]


@lru_cache
def series() -> pd.Series:
    return baseload.load_series(PROCESSED)


@lru_cache
def typical() -> pd.DataFrame:
    return baseload.typical_profile(series())


@lru_cache
def forecast_model() -> xgb.XGBRegressor:
    m = xgb.XGBRegressor()
    m.load_model(_latest("baseload_xgb_*.json"))
    return m


@lru_cache
def forecast_dates() -> list[str]:
    b = pd.read_parquet(PROCESSED / "recon_baseload_15min.parquet", columns=["date_local", "split"])
    full = b[b.split == "test"].groupby("date_local").size()
    return sorted(full[full == 96].index.tolist())


@lru_cache
def real_session_kwh():
    s = pd.read_parquet(PROCESSED / "ev_sessions_clean.parquet", columns=["source", "kwh"])
    return s.loc[s.source == "utrecht", "kwh"].to_numpy()


@lru_cache
def accuracy() -> dict:
    acc = pd.read_csv(_latest("c1_accuracy_*.csv"))
    run = json.loads(_latest("c1_training_*.json").read_text())
    return {"run_id": run["run_id"], "accuracy": json.loads(acc.round(4).to_json(orient="records")),  # NaN -> null
            "q10_coverage_pct": run["metrics"].get("1.3_q10_safe_departure_coverage_%"),
            "clustering": run["metrics"].get("1.2_routine_clustering"),
            "scheduler": run["metrics"].get("1.4_scheduler_scenario", {}).get("results")}
