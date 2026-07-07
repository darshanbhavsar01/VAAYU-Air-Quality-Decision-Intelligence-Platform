"""Open-Meteo weather fetch — free, no API key, any lat/lon (CLAUDE.md §5).

Two endpoints:
  - forecast  (api.open-meteo.com):  recent past (`past_days`) + `forecast_days`
    ahead. Fills the last couple of days and the future the model forecasts into.
  - archive   (archive-api.open-meteo.com): ERA5 hourly reanalysis for a date
    range. This is the honest way to backfill 90 days of REAL weather (unlike
    air quality, historical weather genuinely exists) — used for model training
    features. ERA5 runs a few days behind, so the forecast endpoint's past_days
    covers the recent gap; the (city_id, ts) MERGE reconciles the overlap.

Times are requested in UTC (timezone=GMT) and returned as tz-aware UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from config import HTTP_HEADERS

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
    "surface_pressure",
]


def _parse_hourly(body: dict[str, Any]) -> pd.DataFrame:
    """Turn Open-Meteo's column-oriented `hourly` block into a tidy row frame."""
    hourly = body.get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        return pd.DataFrame(columns=["ts", *HOURLY_VARS])
    df = pd.DataFrame({"ts": pd.to_datetime(times, utc=True)})
    for var in HOURLY_VARS:
        df[var] = hourly.get(var, [None] * len(times))
    return df


def fetch_forecast(
    lat: float, lon: float, past_days: int = 3, forecast_days: int = 2, timeout: int = 30
) -> pd.DataFrame:
    """Recent past + forecast hourly weather. `ts` is tz-aware UTC."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARS),
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timezone": "GMT",
        "wind_speed_unit": "ms",
    }
    resp = requests.get(FORECAST_URL, params=params, headers=HTTP_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return _parse_hourly(resp.json())


def fetch_archive(
    lat: float, lon: float, start_date: str, end_date: str, timeout: int = 60
) -> pd.DataFrame:
    """Historical ERA5 hourly weather for [start_date, end_date] (YYYY-MM-DD)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "GMT",
        "wind_speed_unit": "ms",
    }
    resp = requests.get(ARCHIVE_URL, params=params, headers=HTTP_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return _parse_hourly(resp.json())


if __name__ == "__main__":
    # Smoke test on Bengaluru centroid.
    df = fetch_forecast(12.97, 77.60)
    print(f"forecast rows: {len(df)}  ({df['ts'].min()} .. {df['ts'].max()})")
    now = datetime.now(timezone.utc)
    print("past hours:", (df["ts"] <= now).sum(), "| future hours:", (df["ts"] > now).sum())
    print(df.head(2).to_dict("records"))
