"""Create the VAAYU BigQuery dataset and all raw-table schemas (idempotent).

Run: python infra/bigquery/setup_schema.py
Safe to re-run — every statement is CREATE ... IF NOT EXISTS.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root: make ingest/ importable for the shared bq helper.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "ingest"))

import bq  # noqa: E402

DDL_FILES = ["raw_aqi.sql", "raw_weather.sql", "stations.sql", "aqi_cams.sql", "agent_tables.sql"]


def main() -> None:
    print(f"Ensuring dataset {bq.GCP_PROJECT_ID}.{bq.BQ_DATASET} ({bq.BQ_LOCATION})...")
    bq.ensure_dataset()
    for f in DDL_FILES:
        print(f"Applying {f} ...")
        bq.run_sql_file(f)
    print("Schema ready:", ", ".join(DDL_FILES))


if __name__ == "__main__":
    main()
