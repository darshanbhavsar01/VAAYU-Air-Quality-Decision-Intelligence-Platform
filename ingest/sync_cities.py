"""Sync config/cities.yaml -> BigQuery `cities` dimension table.

Lets SQL (grid generation, interpolation) and the API read the city registry
directly from BigQuery. Idempotent: WRITE_TRUNCATE replaces the table each run,
so it always mirrors the YAML (the source of truth).

Run: python ingest/sync_cities.py
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

import bq
from cities import load_cities

CITIES_COLUMNS = [
    "city_id", "name", "state",
    "lon_min", "lat_min", "lon_max", "lat_max",
    "tier", "priority", "languages", "synced_at",
]


def run() -> int:
    now = pd.Timestamp(datetime.now(timezone.utc))
    rows = []
    for c in load_cities():
        rows.append({
            "city_id": c.city_id, "name": c.name, "state": c.state,
            "lon_min": c.bbox[0], "lat_min": c.bbox[1],
            "lon_max": c.bbox[2], "lat_max": c.bbox[3],
            "tier": c.tier, "priority": c.priority,
            "languages": ",".join(c.languages), "synced_at": now,
        })
    df = pd.DataFrame(rows, columns=CITIES_COLUMNS)
    bq.ensure_dataset()
    n = bq.load_dataframe(df, "cities", write_disposition="WRITE_TRUNCATE")
    print(f"Synced {n} cities to BigQuery `{bq.table_fqn('cities')}`")
    return n


if __name__ == "__main__":
    run()
