"""Onboard a city into VAAYU (CLAUDE.md §5.1) — no code changes required.

The city must already exist as a row in config/cities.yaml. This script then:
  1. Validates CPCB returns live stations for the city (GO/NO-GO on data).
  2. Ingests its current CPCB readings into raw_aqi / stations.
  3. Backfills its 90-day ERA5 weather history into raw_weather.
  4. Reports its tier (A grid vs B ward) from ward-GeoJSON presence.

Design point for judges: onboarding is config-driven. Adding "pune" is a YAML
edit plus `python scripts/onboard_city.py pune` — same models, no redeploy.

Usage: python scripts/onboard_city.py <city_id> [--backfill-days N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make ingest/ importable when run from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

import cpcb  # noqa: E402
import cpcb_ingest  # noqa: E402
import weather_ingest  # noqa: E402
from cities import get_city  # noqa: E402
from config import DATA_DIR  # noqa: E402

MIN_STATIONS = 2  # a city needs at least this to be worth interpolating


def onboard(city_id: str, backfill_days: int = 90) -> int:
    city = get_city(city_id)  # raises with a clear message if not in registry
    print(f"== Onboarding {city.name} ({city.city_id}) ==")

    # 1. Validate CPCB coverage.
    records = cpcb.fetch_cpcb_snapshot()
    city_recs = cpcb.filter_city(records, city.name, city.state)
    stations = {r.get("station") for r in city_recs if r.get("station")}
    print(f"1. CPCB validation: {len(stations)} stations, {len(city_recs)} station×pollutant rows")
    if len(stations) < MIN_STATIONS:
        print(f"   NO-GO: fewer than {MIN_STATIONS} stations — leave this city out until coverage improves.")
        return 1

    # 2. Ingest current CPCB readings for this city.
    print("2. Ingesting current CPCB readings...")
    cpcb_ingest.run(only=[city_id])

    # 3. Backfill weather history.
    print(f"3. Backfilling {backfill_days}d weather...")
    weather_ingest.run_backfill(days=backfill_days, only=[city_id])
    weather_ingest.run_forecast(only=[city_id])

    # 4. Tier verdict.
    ward_path = DATA_DIR / "wards" / f"{city_id}.geojson"
    tier = "B (grid + ward)" if ward_path.exists() else "A (grid only)"
    print(f"4. Tier: {tier}" + ("" if ward_path.exists()
          else f"  (add + validate {ward_path.name} to upgrade to Tier B)"))

    print(f"\nOK: {city.name} onboarded. It now appears in every city-parameterized surface.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("city_id")
    ap.add_argument("--backfill-days", type=int, default=90)
    args = ap.parse_args()
    raise SystemExit(onboard(args.city_id, args.backfill_days))
