"""CAMS air-quality fetch via Open-Meteo (free, no key).

Provides MODELLED hourly pollutants (pm2_5, pm10, NO2, SO2, O3, CO) for any
lat/lon, historical (start/end back to ~2022) or forecast. This is VAAYU's
training-history source because CPCB has no historical API (CLAUDE.md §5 /
docs/LIMITATIONS.md). Always stored separately from CPCB with a source label.

Open-Meteo supports multiple coordinates per request (comma-separated), so we
fetch many stations in a few batched calls rather than one call per station.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd
import requests

from config import HTTP_HEADERS

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

HOURLY_VARS = [
    "pm2_5",
    "pm10",
    "nitrogen_dioxide",
    "sulphur_dioxide",
    "ozone",
    "carbon_monoxide",
]

# Open-Meteo accepts many locations per call; keep batches modest to stay well
# within URL length and free-tier limits.
BATCH_SIZE = 40


def _parse_one(station_id: str, city_id: str, obj: dict) -> pd.DataFrame:
    hourly = obj.get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        return pd.DataFrame()
    df = pd.DataFrame({"ts": pd.to_datetime(times, utc=True)})
    for var in HOURLY_VARS:
        df[var] = hourly.get(var, [None] * len(times))
    df.insert(0, "station_id", station_id)
    df.insert(0, "city_id", city_id)
    df["latitude"] = obj.get("latitude")
    df["longitude"] = obj.get("longitude")
    return df


def fetch_air_quality(
    points: list[tuple[str, str, float, float]],
    start_date: str | None = None,
    end_date: str | None = None,
    past_days: int | None = None,
    forecast_days: int | None = None,
    timeout: int = 90,
) -> pd.DataFrame:
    """Fetch hourly CAMS pollutants for many stations.

    points: list of (city_id, station_id, lat, lon).
    Either pass start_date/end_date (historical) or past_days/forecast_days.
    Returns a long DataFrame: city_id, station_id, ts, <pollutants>, lat, lon.
    Results are matched to input points by request order (not the API's
    grid-snapped echoed coords).
    """
    frames: list[pd.DataFrame] = []
    for batch in _chunks(points, BATCH_SIZE):
        lats = ",".join(str(p[2]) for p in batch)
        lons = ",".join(str(p[3]) for p in batch)
        params = {
            "latitude": lats,
            "longitude": lons,
            "hourly": ",".join(HOURLY_VARS),
            "timezone": "GMT",
        }
        if start_date and end_date:
            params["start_date"] = start_date
            params["end_date"] = end_date
        if past_days is not None:
            params["past_days"] = past_days
        if forecast_days is not None:
            params["forecast_days"] = forecast_days

        resp = requests.get(AQ_URL, params=params, headers=HTTP_HEADERS, timeout=timeout)
        resp.raise_for_status()
        body = resp.json()
        # Single-location responses are an object; multi-location are a list.
        objs = body if isinstance(body, list) else [body]
        for (city_id, station_id, _lat, _lon), obj in zip(batch, objs):
            frames.append(_parse_one(station_id, city_id, obj))

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _chunks(seq: list, n: int) -> Iterable[list]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


if __name__ == "__main__":
    pts = [("bengaluru", "test_blr", 12.97, 77.60), ("delhi", "test_del", 28.64, 77.10)]
    df = fetch_air_quality(pts, start_date="2026-06-01", end_date="2026-06-03")
    print("rows:", len(df))
    print(df.groupby("station_id")["ts"].agg(["count", "min", "max"]))
    print(df.head(2).to_dict("records"))
