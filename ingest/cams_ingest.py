"""CAMS ingest job — backfill/refresh modelled air quality at station locations.

Reads the discovered stations from BigQuery, fetches CAMS hourly pollutants at
each station's real coordinates, and upserts into aqi_cams (idempotent on
(station_id, ts)). This is the training-history backbone for Phase 2 models.

Usage:
  python ingest/cams_ingest.py backfill [days]   # default 90 (historical)
  python ingest/cams_ingest.py forecast          # past_days=3 + forecast_days=2
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

import bq
import cams

SOURCE = "cams_openmeteo"
ARCHIVE_LAG_DAYS = 4  # CAMS reanalysis lag; forecast mode covers the recent gap

AQI_CAMS_COLUMNS = [
    "city_id", "station_id", "latitude", "longitude", "ts",
    "pm2_5", "pm10", "nitrogen_dioxide", "sulphur_dioxide", "ozone", "carbon_monoxide",
    "source", "ingested_at",
]


def _station_points() -> list[tuple[str, str, float, float]]:
    """(city_id, station_id, lat, lon) for every station with coordinates."""
    sql = f"""
    SELECT city_id, station_id, latitude, longitude
    FROM `{bq.table_fqn('stations')}`
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    ORDER BY city_id, station_id
    """
    rows = bq.client().query(sql, location=bq.BQ_LOCATION).result()
    return [(r.city_id, r.station_id, r.latitude, r.longitude) for r in rows]


def _finalize(df: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=AQI_CAMS_COLUMNS)
    df = df.copy()
    df["source"] = SOURCE
    df["ingested_at"] = now
    return df[AQI_CAMS_COLUMNS]


CHUNK_DAYS = 45  # date-range chunk size to stay under Open-Meteo free-tier request weight


def run_backfill(days: int = 90, chunk_days: int = CHUNK_DAYS) -> dict[str, int]:
    """Backfill `days` of CAMS history, date-chunked and merged per chunk so a
    rate-limit late in the run never loses earlier progress (idempotent MERGE)."""
    now = pd.Timestamp(datetime.now(timezone.utc))
    final_end = (now - timedelta(days=ARCHIVE_LAG_DAYS)).date()
    start = (now - timedelta(days=days)).date()
    points = _station_points()
    print(f"CAMS backfill {start}..{final_end} for {len(points)} stations "
          f"(in {chunk_days}-day chunks)")

    total = 0
    chunk_start = start
    while chunk_start <= final_end:
        chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), final_end)
        raw = cams.fetch_air_quality(
            points, start_date=chunk_start.isoformat(), end_date=chunk_end.isoformat()
        )
        df = _finalize(raw, now)
        n = bq.load_and_merge(df, "_staging_aqi_cams", "merge_aqi_cams.sql")
        print(f"  {chunk_start}..{chunk_end}: merged {n} rows")
        total += n
        chunk_start = chunk_end + timedelta(days=1)
    return {"rows": total, "stations": len(points)}


def run_forecast() -> dict[str, int]:
    now = pd.Timestamp(datetime.now(timezone.utc))
    points = _station_points()
    print(f"CAMS forecast (past 3d + 2d ahead) for {len(points)} stations")
    raw = cams.fetch_air_quality(points, past_days=3, forecast_days=2)
    df = _finalize(raw, now)
    n = bq.load_and_merge(df, "_staging_aqi_cams", "merge_aqi_cams.sql")
    print(f"  merged {n} CAMS rows")
    return {"rows": n, "stations": len(points)}


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "backfill"
    bq.ensure_dataset()
    if mode == "backfill":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        print("Done:", run_backfill(days))
    elif mode == "forecast":
        print("Done:", run_forecast())
    else:
        raise SystemExit(f"Unknown mode {mode!r}. Use 'backfill' or 'forecast'.")
