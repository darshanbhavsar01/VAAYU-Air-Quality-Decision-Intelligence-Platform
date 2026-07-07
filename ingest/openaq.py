"""OpenAQ v3 probe — used in Phase 0 to de-risk historical backfill.

data.gov.in gives only a live CPCB snapshot, so the 90-day history that the
forecast models need comes from OpenAQ (which mirrors many CPCB CAAQMS
stations). This module answers the Phase 0 question: for Bengaluru, how many
locations does OpenAQ expose, and how deep/complete is their daily history?
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from config import OPENAQ_API_KEY, OPENAQ_BASE, require

# Bengaluru bounding box (lon_min, lat_min, lon_max, lat_max).
BENGALURU_BBOX = "77.35,12.75,77.85,13.20"


def _headers() -> dict[str, str]:
    return {"X-API-Key": require("OPENAQ_API_KEY", OPENAQ_API_KEY)}


def fetch_locations(bbox: str = BENGALURU_BBOX, timeout: int = 30) -> list[dict[str, Any]]:
    """List OpenAQ locations within a bounding box (paginated)."""
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        resp = requests.get(
            f"{OPENAQ_BASE}/locations",
            headers=_headers(),
            params={"bbox": bbox, "limit": 100, "page": page},
            timeout=timeout,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            break
        out.extend(results)
        if len(results) < 100:
            break
        page += 1
    return out


def fetch_sensor_daily_coverage(
    sensor_id: int, days: int = 30, timeout: int = 30
) -> list[dict[str, Any]]:
    """Fetch daily aggregates for one sensor over the last `days` days.

    Used to measure how complete a station's recent history is (how many of
    the last `days` calendar days actually have data).
    """
    date_to = datetime.now(timezone.utc)
    date_from = date_to - timedelta(days=days)
    resp = requests.get(
        f"{OPENAQ_BASE}/sensors/{sensor_id}/days",
        headers=_headers(),
        params={
            "date_from": date_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date_to": date_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": days + 5,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


if __name__ == "__main__":
    locs = fetch_locations()
    print(f"OpenAQ locations in Bengaluru bbox: {len(locs)}")
    for loc in locs[:5]:
        sensors = loc.get("sensors", [])
        params = sorted({s.get("parameter", {}).get("name") for s in sensors})
        print(f"  #{loc.get('id')} {loc.get('name')!r} — params: {params}")
