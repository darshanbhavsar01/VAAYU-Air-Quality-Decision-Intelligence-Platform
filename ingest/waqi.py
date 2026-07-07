"""WAQI (aqicn.org) — secondary cross-validation source (OpenAQ replacement).

OpenAQ v3 requires email verification that has been unreliable to receive;
WAQI issues a token instantly at https://aqicn.org/data-platform/token/.

FREE-TIER REALITY (verified 2026-07, documented in docs/LIMITATIONS.md):
  - `/feed/{cityname}/`  ✅ works — returns the city's dominant-station live
    reading (overall AQI + per-pollutant sub-indices in `iaqi`).
  - `/map/bounds/` and `/feed/geo:lat;lng/`  ❌ NOT reliably served on the free
    token — they return Delhi stations or "can not connect" for most cities.
    So WAQI cannot be used for multi-station density / discovery on this tier.

Consequence: WAQI's role in VAAYU is narrow — a coarse independent sanity
check that "an outside source also reports elevated/normal air for this city,"
NOT a station inventory and NOT a historical archive. CPCB via data.gov.in is
the primary source and carries the real station coverage (10–45 per metro).
Real 90-day history accrues from VAAYU's own hourly ingest (CLAUDE.md Phase 1).
"""
from __future__ import annotations

from typing import Any

import requests

from config import HTTP_HEADERS, require

try:
    from config import WAQI_API_TOKEN  # type: ignore
except ImportError:
    WAQI_API_TOKEN = ""

WAQI_BASE = "https://api.waqi.info"


def _token() -> str:
    return require("WAQI_API_TOKEN", WAQI_API_TOKEN)


def fetch_city_feed(city_name: str, timeout: int = 30) -> dict[str, Any]:
    """Current AQI feed for a named city's dominant station (free-tier reliable).

    Returns WAQI's `data` block: {aqi, city:{name,geo}, iaqi:{pm25:{v},...}, time}.
    Raises RuntimeError if WAQI can't resolve/connect for the city.
    """
    resp = requests.get(
        f"{WAQI_BASE}/feed/{city_name}/",
        params={"token": _token()},
        headers=HTTP_HEADERS,
        timeout=timeout,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "ok":
        raise RuntimeError(f"WAQI error for {city_name!r}: {body.get('data', body)}")
    return body["data"]


def city_crosscheck(city_name: str, timeout: int = 30) -> dict[str, Any]:
    """Coarse independent sanity check for one city.

    Returns dominant AQI, the PM2.5 US-AQI sub-index (if present), which station
    WAQI resolved to, and the reading timestamp — enough to say "an outside
    source corroborates a live signal for this city." Never treated as ground
    truth against CPCB µg/m³ (different units/scales).
    """
    data = fetch_city_feed(city_name, timeout=timeout)
    iaqi = data.get("iaqi", {}) or {}
    return {
        "resolved_station": (data.get("city", {}) or {}).get("name"),
        "dominant_aqi": data.get("aqi"),
        "pm25_subindex": (iaqi.get("pm25", {}) or {}).get("v"),
        "time": (data.get("time", {}) or {}).get("s"),
    }


if __name__ == "__main__":
    from cities import load_cities

    for c in load_cities():
        # Try the city_id slug and the display name; either may resolve.
        for candidate in (c.city_id, c.name.lower()):
            try:
                res = city_crosscheck(candidate)
                print(f"{c.name:12s} via {candidate!r}: {res}")
                break
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
        else:
            print(f"{c.name:12s}: unresolved — {last}")
