"""CPCB ingest job — one national snapshot -> raw_aqi + stations (idempotent).

Fetches the CPCB live snapshot once, filters it to every active city in
config/cities.yaml, and upserts readings into BigQuery via the staging+MERGE
pattern (re-running the same hour never duplicates rows — CLAUDE.md §11).

Run locally:  python ingest/cpcb_ingest.py
On Cloud Run:  same entrypoint; ADC comes from the job's service account.
This is the hourly job body for Phase 1's live ingest.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

import bq
import cpcb
from cities import load_cities

SOURCE = "cpcb_datagovin"

RAW_AQI_COLUMNS = [
    "city_id", "station_id", "station", "state", "latitude", "longitude",
    "pollutant", "ts", "min_value", "max_value", "avg_value", "source", "ingested_at",
]
STATIONS_COLUMNS = [
    "station_id", "station", "city_id", "state", "latitude", "longitude",
    "first_seen", "last_seen",
]


def build_frames(
    records: list[dict], now: pd.Timestamp, only: list[str] | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Transform CPCB records into (raw_aqi, stations) frames.

    `only` scopes to specific city_ids (used by onboarding); default = all
    registry cities out of the one national snapshot.
    """
    aqi_rows: list[dict] = []
    station_rows: dict[str, dict] = {}

    for city in load_cities(only=only):
        for r in cpcb.filter_city(records, city.name, city.state):
            station = r.get("station") or r.get("station_name")
            pollutant = r.get("pollutant_id") or r.get("pollutant") or r.get("parameter")
            ts_ist = cpcb.parse_cpcb_timestamp(str(r.get("last_update", "")))
            if not (station and pollutant and ts_ist):
                continue  # unusable row (no station / pollutant / timestamp)
            sid = cpcb.station_slug(station)
            lat = cpcb.safe_float(r.get("latitude"))
            lon = cpcb.safe_float(r.get("longitude"))
            ts_utc = pd.Timestamp(ts_ist).tz_convert("UTC")

            aqi_rows.append(
                {
                    "city_id": city.city_id,
                    "station_id": sid,
                    "station": station,
                    "state": r.get("state"),
                    "latitude": lat,
                    "longitude": lon,
                    "pollutant": str(pollutant),
                    "ts": ts_utc,
                    "min_value": cpcb.safe_float(r.get("min_value") or r.get("pollutant_min")),
                    "max_value": cpcb.safe_float(r.get("max_value") or r.get("pollutant_max")),
                    "avg_value": cpcb.safe_float(r.get("avg_value") or r.get("pollutant_avg")),
                    "source": SOURCE,
                    "ingested_at": now,
                }
            )
            # One station row per station_id (dimension). first_seen refined by MERGE.
            station_rows[sid] = {
                "station_id": sid,
                "station": station,
                "city_id": city.city_id,
                "state": r.get("state"),
                "latitude": lat,
                "longitude": lon,
                "first_seen": now,
                "last_seen": now,
            }

    aqi_df = pd.DataFrame(aqi_rows, columns=RAW_AQI_COLUMNS)
    stations_df = pd.DataFrame(list(station_rows.values()), columns=STATIONS_COLUMNS)
    return aqi_df, stations_df


def run(only: list[str] | None = None) -> dict[str, int]:
    now = pd.Timestamp(datetime.now(timezone.utc))
    print("Fetching CPCB national snapshot...")
    records = cpcb.fetch_cpcb_snapshot()
    scope = "all registry cities" if only is None else ", ".join(only)
    print(f"  {len(records)} records; filtering to {scope}...")

    aqi_df, stations_df = build_frames(records, now, only=only)
    print(f"  {len(aqi_df)} readings across {stations_df.shape[0]} stations")

    bq.ensure_dataset()
    staged_aqi = bq.load_and_merge(aqi_df, "_staging_raw_aqi", "merge_raw_aqi.sql")
    staged_stations = bq.load_and_merge(stations_df, "_staging_stations", "merge_stations.sql")
    print(f"  merged {staged_aqi} readings, {staged_stations} stations into BigQuery")

    return {"readings": staged_aqi, "stations": staged_stations}


if __name__ == "__main__":
    result = run()
    print("Done:", result)
