"""VAAYU hourly refresh pipeline — the Cloud Run Job entrypoint.

Runs the full sequence that keeps the live product current:
  1. CPCB ingest        -> raw_aqi + stations (fresh station readings & health)
  2. weather forecast   -> raw_weather (recent + short forecast)
  3. CAMS forecast      -> aqi_cams   (recent + short forecast pollutants)
  4. sync cities        -> cities table (registry mirror)
  5. rebuild features   -> features   (latest hours included)
  6. station_forecast   -> ML.PREDICT both models per station
  7. interpolate        -> city_grid_surface (IDW grid + confidence)

Idempotent throughout (MERGE / CREATE OR REPLACE), so re-runs are safe.
Triggered hourly by Cloud Scheduler. Run locally: python pipeline.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "ingest"))

import bq  # noqa: E402
import cams_ingest  # noqa: E402
import cpcb_ingest  # noqa: E402
import sync_cities  # noqa: E402
import weather_ingest  # noqa: E402

ML = REPO / "ml"


def _step(label: str, fn) -> None:
    t = time.time()
    print(f"[pipeline] {label} ...", flush=True)
    fn()
    print(f"[pipeline] {label} done in {time.time()-t:.0f}s", flush=True)


def main() -> None:
    t0 = time.time()
    bq.ensure_dataset()
    _step("1/7 CPCB ingest", lambda: cpcb_ingest.run())
    _step("2/7 weather forecast", lambda: weather_ingest.run_forecast())
    _step("3/7 CAMS forecast", lambda: cams_ingest.run_forecast())
    _step("4/7 sync cities", lambda: sync_cities.run())
    _step("5/7 rebuild features", lambda: bq.run_sql_file(str(ML / "features.sql")))
    _step("6/7 station_forecast", lambda: bq.run_sql_file(str(ML / "station_forecast.sql")))
    _step("7/7 interpolate grid", lambda: bq.run_sql_file(str(ML / "interpolate.sql")))
    print(f"[pipeline] ALL DONE in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
