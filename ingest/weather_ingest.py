"""Weather ingest job — Open-Meteo -> raw_weather (idempotent, per city centroid).

Two modes:
  forecast  (hourly job): recent past + short forecast for every active city.
            is_forecast=TRUE for hours after now; a later run (or archive
            backfill) overwrites a forecast hour with the real observation.
  backfill  (one-time / occasional): 90-day ERA5 history per city — the real
            weather backfill that feeds model training features (CLAUDE.md §6.2).

Usage:
  python ingest/weather_ingest.py forecast
  python ingest/weather_ingest.py backfill [days]      # default 90
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

import bq
import weather
from cities import City, load_cities

RAW_WEATHER_COLUMNS = [
    "city_id", "latitude", "longitude", "ts",
    "temperature_2m", "relative_humidity_2m", "wind_speed_10m",
    "wind_direction_10m", "precipitation", "surface_pressure",
    "is_forecast", "source", "ingested_at",
]

# ERA5 archive lags a few days; forecast past_days covers the recent gap.
ARCHIVE_LAG_DAYS = 4


def _centroid(city: City) -> tuple[float, float]:
    lon = (city.bbox[0] + city.bbox[2]) / 2
    lat = (city.bbox[1] + city.bbox[3]) / 2
    return lat, lon


def _to_frame(city: City, hourly: pd.DataFrame, lat: float, lon: float,
              source: str, now: pd.Timestamp) -> pd.DataFrame:
    if hourly.empty:
        return pd.DataFrame(columns=RAW_WEATHER_COLUMNS)
    df = hourly.copy()
    df["city_id"] = city.city_id
    df["latitude"] = lat
    df["longitude"] = lon
    df["is_forecast"] = df["ts"] > now
    df["source"] = source
    df["ingested_at"] = now
    return df[RAW_WEATHER_COLUMNS]


def run_forecast() -> dict[str, int]:
    now = pd.Timestamp(datetime.now(timezone.utc))
    bq.ensure_dataset()
    total = 0
    for city in load_cities():
        lat, lon = _centroid(city)
        hourly = weather.fetch_forecast(lat, lon)
        df = _to_frame(city, hourly, lat, lon, "open_meteo", now)
        n = bq.load_and_merge(df, "_staging_raw_weather", "merge_raw_weather.sql")
        print(f"  {city.name:12s}: {n} hourly rows")
        total += n
    return {"rows": total}


def run_backfill(days: int = 90) -> dict[str, int]:
    now = pd.Timestamp(datetime.now(timezone.utc))
    end = (now - timedelta(days=ARCHIVE_LAG_DAYS)).strftime("%Y-%m-%d")
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"Backfilling weather {start} .. {end} ({days}d ERA5) per city")
    bq.ensure_dataset()
    total = 0
    for city in load_cities():
        lat, lon = _centroid(city)
        hourly = weather.fetch_archive(lat, lon, start, end)
        df = _to_frame(city, hourly, lat, lon, "open_meteo_archive", now)
        # Archive rows are all historical observations, never forecasts.
        df["is_forecast"] = False
        n = bq.load_and_merge(df, "_staging_raw_weather", "merge_raw_weather.sql")
        print(f"  {city.name:12s}: {n} hourly rows")
        total += n
    return {"rows": total}


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "forecast"
    if mode == "forecast":
        print("Done:", run_forecast())
    elif mode == "backfill":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        print("Done:", run_backfill(days))
    else:
        raise SystemExit(f"Unknown mode {mode!r}. Use 'forecast' or 'backfill'.")
