"""CPCB CAAQMS real-time fetch via data.gov.in.

The data.gov.in resource returns the LATEST hourly snapshot for every
station in India (one row per station×pollutant). It is not a historical
archive — 90-day history is sourced separately (OpenAQ) in Phase 1. For
Phase 0 this snapshot tells us: how many Bengaluru stations exist, which
pollutants they report, and how fresh each reading is (staleness).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

# CPCB data.gov.in timestamps (`last_update`) are in India Standard Time
# (UTC+5:30) with no tz suffix. Parsing them naively as UTC puts every reading
# ~5.5h in the future and breaks staleness math — always attach IST.
IST = timezone(timedelta(hours=5, minutes=30))

from config import (
    CPCB_RESOURCE_ID,
    DATA_GOV_IN_API_KEY,
    DATA_GOV_IN_BASE,
    HTTP_HEADERS,
    require,
)


def fetch_cpcb_snapshot(limit: int = 5000, timeout: int = 30) -> list[dict[str, Any]]:
    """Fetch the full current CPCB snapshot (all India). Returns list of records.

    Observed schema (2026-07, resource 3b01bcb8-...):
      {country, state, city, station, last_update (IST, "DD-MM-YYYY HH:MM:SS"),
       pollutant_id, min_value, max_value, avg_value  (any may be the string "NA"),
       latitude, longitude  (strings)}
    One row per station×pollutant. Field names vary slightly across data.gov.in
    revisions; callers should tolerate missing keys.
    """
    require("DATA_GOV_IN_API_KEY", DATA_GOV_IN_API_KEY)
    url = f"{DATA_GOV_IN_BASE}/{CPCB_RESOURCE_ID}"
    params = {
        "api-key": DATA_GOV_IN_API_KEY,
        "format": "json",
        "limit": limit,
    }
    resp = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()
    return body.get("records", [])


def parse_cpcb_timestamp(raw: str) -> datetime | None:
    """Parse a CPCB `last_update` string as IST-aware datetime (or None).

    Returned value is timezone-aware, so callers can safely compare it against
    `datetime.now(timezone.utc)` to compute reading age / staleness.
    """
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(raw).strip(), fmt).replace(tzinfo=IST)
        except (ValueError, AttributeError):
            continue
    return None


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
