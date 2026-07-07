"""CPCB CAAQMS real-time fetch via data.gov.in.

The data.gov.in resource returns the LATEST hourly snapshot for every
station in India (one row per station×pollutant). It is not a historical
archive — 90-day history is sourced separately (OpenAQ) in Phase 1. For
Phase 0 this snapshot tells us: how many Bengaluru stations exist, which
pollutants they report, and how fresh each reading is (staleness).
"""
from __future__ import annotations

from typing import Any

import requests

from config import (
    CPCB_RESOURCE_ID,
    DATA_GOV_IN_API_KEY,
    DATA_GOV_IN_BASE,
    require,
)


def fetch_cpcb_snapshot(limit: int = 5000, timeout: int = 30) -> list[dict[str, Any]]:
    """Fetch the full current CPCB snapshot (all India). Returns list of records.

    Each record is roughly:
      {country, state, city, station, last_update,
       pollutant_id, pollutant_min, pollutant_max, pollutant_avg,
       latitude, longitude}
    Field names vary slightly across data.gov.in revisions; callers should
    tolerate missing keys.
    """
    require("DATA_GOV_IN_API_KEY", DATA_GOV_IN_API_KEY)
    url = f"{DATA_GOV_IN_BASE}/{CPCB_RESOURCE_ID}"
    params = {
        "api-key": DATA_GOV_IN_API_KEY,
        "format": "json",
        "limit": limit,
    }
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()
    return body.get("records", [])


def filter_city(records: list[dict[str, Any]], city: str, state: str) -> list[dict[str, Any]]:
    """Filter CPCB records to one city (case-insensitive), falling back to state."""
    city_l, state_l = city.lower(), state.lower()
    out = [r for r in records if str(r.get("city", "")).lower() == city_l]
    if not out:  # some revisions omit city; fall back to state scan
        out = [r for r in records if str(r.get("state", "")).lower() == state_l]
    return out


if __name__ == "__main__":
    from cities import load_cities

    recs = fetch_cpcb_snapshot()
    print(f"Fetched {len(recs)} total CPCB records (all India).")
    if recs:
        print("Sample record keys:", sorted(recs[0].keys()))
    print()
    for c in load_cities():
        n = len(filter_city(recs, c.name, c.state))
        print(f"  {c.name:12s} ({c.city_id}): {n} station×pollutant records")
