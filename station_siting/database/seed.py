"""Build the C2 database (c2.db) from the cleaned layers. Run ONCE with the geo environment:

    python -m station_siting.database.seed

Tables: hexagons (H3 res 8, demand per period), candidates (real sites + criteria), substations (CEB plan),
chargers (OSM), meta (district outline, period weights). optimization_runs is created by the API.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

from station_siting.demand import index

C2 = Path(__file__).resolve().parents[1]
DB_URL = f"sqlite:///{(C2 / 'database' / 'c2.db').as_posix()}"


def main() -> None:
    data = index.build(C2 / "data" / "processed")
    eng = create_engine(DB_URL)
    with eng.begin() as con:
        for t in ("hexagons", "candidates", "substations", "chargers", "meta"):
            con.execute(text(f"DROP TABLE IF EXISTS {t}"))
    data["hexes"].to_sql("hexagons", eng, index=False)
    data["candidates"].to_sql("candidates", eng, index=True, index_label="id")
    data["substations"].to_sql("substations", eng, index=False)
    data["chargers"].to_sql("chargers", eng, index=False)
    meta = {"district_geojson": data["district_geojson"],
            "period_weights": index.PERIOD_WEIGHTS.to_json(orient="index"),
            "periods": json.dumps(index.PERIODS), "h3_resolution": str(index.RES_H3),
            "seeded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with eng.begin() as con:
        con.execute(text("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"))
        for k, v in meta.items():
            con.execute(text("INSERT INTO meta VALUES (:k, :v)"), {"k": k, "v": v})
    print({k: len(v) for k, v in data.items() if hasattr(v, "__len__") and not isinstance(v, str)})


if __name__ == "__main__":
    main()
