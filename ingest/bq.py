"""Shared BigQuery helpers for VAAYU ingest jobs.

Keeps all SQL in versioned .sql files (CLAUDE.md §11 — never inline SQL in
Python) and centralises the client, table naming, staging-load, and the
load->MERGE idempotency pattern every ingest job uses.

Idempotency pattern (why staging + MERGE, not INSERT):
  Re-running an hourly job must never duplicate rows (CLAUDE.md §11). We load
  the batch into a per-job staging table (WRITE_TRUNCATE) then MERGE it into
  the target on the natural key. Load jobs are free; the MERGE scans only tiny
  tables, staying inside the BigQuery free tier.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from google.cloud import bigquery

from config import BQ_DATASET, GCP_PROJECT_ID, REPO_ROOT, require

BQ_LOCATION = "asia-south1"  # match sibling `varuna`; India data residency (pitch point)
SQL_DIR = REPO_ROOT / "infra" / "bigquery"

_client: bigquery.Client | None = None


def client() -> bigquery.Client:
    global _client
    if _client is None:
        require("GCP_PROJECT_ID", GCP_PROJECT_ID)
        _client = bigquery.Client(project=GCP_PROJECT_ID, location=BQ_LOCATION)
    return _client


def table_fqn(name: str) -> str:
    """Fully-qualified `project.dataset.table` (backtick-safe)."""
    return f"{GCP_PROJECT_ID}.{BQ_DATASET}.{name}"


def ensure_dataset() -> None:
    c = client()
    ds_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}"
    ds = bigquery.Dataset(ds_id)
    ds.location = BQ_LOCATION
    ds.description = "VAAYU — nationwide air-quality decision intelligence (raw feeds, surfaces, models)"
    c.create_dataset(ds, exists_ok=True)


def run_sql_file(filename: str, **params: str) -> bigquery.table.RowIterator:
    """Execute a .sql file from infra/bigquery/, substituting {project}/{dataset}/... placeholders."""
    sql = (SQL_DIR / filename).read_text(encoding="utf-8")
    sql = sql.format(project=GCP_PROJECT_ID, dataset=BQ_DATASET, **params)
    return client().query(sql, location=BQ_LOCATION).result()


def load_dataframe(df: pd.DataFrame, table: str, write_disposition: str = "WRITE_TRUNCATE") -> int:
    """Load a DataFrame into a (staging) table. Returns rows loaded."""
    if df.empty:
        return 0
    job_config = bigquery.LoadJobConfig(write_disposition=write_disposition)
    job = client().load_table_from_dataframe(
        df, table_fqn(table), job_config=job_config, location=BQ_LOCATION
    )
    job.result()
    return len(df)


def load_and_merge(df: pd.DataFrame, staging_table: str, merge_sql_file: str) -> int:
    """Load `df` into a staging table, then run the MERGE SQL that upserts it
    into its target. Returns rows staged (0 if df empty -> no-op).
    """
    n = load_dataframe(df, staging_table)
    if n == 0:
        return 0
    run_sql_file(merge_sql_file)
    return n


def count_rows(table: str, where: str = "") -> int:
    clause = f" WHERE {where}" if where else ""
    sql = f"SELECT COUNT(*) AS n FROM `{table_fqn(table)}`{clause}"
    return list(client().query(sql, location=BQ_LOCATION).result())[0].n


if __name__ == "__main__":
    print("Project:", GCP_PROJECT_ID, "| Dataset:", BQ_DATASET, "| Location:", BQ_LOCATION)
    ensure_dataset()
    print("Dataset ensured.")
