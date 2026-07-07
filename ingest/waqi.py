"""WAQI (aqicn.org) — OpenAQ replacement for cross-validation / secondary coverage.

OpenAQ v3 requires email verification that has been unreliable to receive;
WAQI issues a token instantly at https://aqicn.org/data-platform/token/ with
no confirmation step, so it's the pragmatic swap for Phase 0/1.

Important honesty note (goes in docs/LIMITATIONS.md too): WAQI's free API
exposes CURRENT station readings well (via map/bounds and city feed), but is
NOT a deep historical archive like OpenAQ aimed to be. It is used here for:
  1. Cross-validating CPCB live readings against an independent mirror.
  2. Discovering additional monitoring stations per city (station density
     check for the Tier A/B decision).
Actual 90-day history is built by VAAYU's own hourly ingest from day 1
onward (CLAUDE.md Phase 1) — there is no shortcut to pre-existing deep
history without a paid archive, so the backfill window grows with the
project rather than starting pre-filled. This gets stated in the pitch.
"""
from __future__ import annotations

from typing import Any

import requests

from config import require

try:
    from config import WAQI_API_TOKEN  # type: ignore
except ImportError:
    WAQI_API_TOKEN = ""

WAQI_BASE = "https://api.waqi.info"


def _token() -> str:
    return require("WAQI_API_TOKEN", WAQI_API_TOKEN)


def fetch_city_feed(city_name: str, timeout: int = 30) -> dict[str, Any]:
    """Current AQI feed for a named city's dominant station."""
    resp = requests.get(
        f"{WAQI_BASE}/feed/{city_name}/", params={"token": _token()}, timeout=timeout
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "ok":
        raise RuntimeError(f"WAQI error for {city_name!r}: {body}")
    return body["data"]


def fetch_stations_in_bbox(
    lon_min: float, lat_min: float, lon_max: float, lat_max: float, timeout: int = 30
) -> list[dict[str, Any]]:
    """All monitoring stations WAQI knows about within a bounding box, with live AQI.

    latlng format is lat1,lon1,lat2,lon2 (south-west, north-east corners).
    """
    latlng = f"{lat_min},{lon_min},{lat_max},{lon_max}"
    resp = requests.get(
        f"{WAQI_BASE}/map/bounds/",
        params={"latlng": latlng, "token": _token()},
        timeout=timeout,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "ok":
        raise RuntimeError(f"WAQI bounds error: {body}")
    return body["data"]


if __name__ == "__main__":
    from cities import load_cities

    for c in load_cities():
        try:
            stations = fetch_stations_in_bbox(*c.bbox)
        except Exception as e:  # noqa: BLE001
            print(f"{c.name}: ERROR {type(e).__name__}: {e}")
            continue
        print(f"{c.name}: {len(stations)} WAQI stations in bbox")
        for s in stations[:3]:
            print(f"    {s.get('station', {}).get('name')} — AQI {s.get('aqi')}")
