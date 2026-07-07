"""Phase 0 — De-risk. Audit CPCB Bengaluru data quality and OpenAQ backfill.

Produces a GO / CAUTION / NO-GO recommendation for the forecast product, and
writes a human-readable report to docs/PHASE0_AUDIT.md plus a machine-readable
snapshot to evaluation/results/phase0_audit.json.

The two data sources answer different questions:
  - CPCB live snapshot (data.gov.in): how many Bengaluru stations exist right
    now, what they measure, and how fresh (staleness) each reading is.
  - OpenAQ v3: whether we can actually get the 90-day history the models need.

Run: python ingest/phase0_audit.py
Each source is independent — a missing key for one still lets the other run.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from typing import Any

import config
import cpcb
import openaq

# --- GO/NO-GO thresholds (documented so judges can see the bar we set) ---
MIN_STATIONS_GO = 8          # fewer than this and IDW interpolation is too sparse
MIN_STATIONS_CAUTION = 5
STALE_HOURS = 3              # CLAUDE.md sentinel definition of "stale"
MIN_HISTORY_COVERAGE = 0.70  # fraction of last 30 days with data to call backfill viable


# ---------------------------------------------------------------------------
# CPCB snapshot audit
# ---------------------------------------------------------------------------
def _parse_last_update(raw: str) -> datetime | None:
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            continue
    return None


def audit_cpcb() -> dict[str, Any]:
    try:
        records = cpcb.fetch_cpcb_snapshot()
    except SystemExit as e:
        return {"available": False, "reason": str(e)}
    except Exception as e:  # noqa: BLE001 — de-risk script wants the reason, not a stack
        return {"available": False, "reason": f"{type(e).__name__}: {e}"}

    city_recs = cpcb.filter_city(records, config.CITY_NAME, config.CITY_STATE)
    now = datetime.now(timezone.utc)

    stations: dict[str, dict[str, Any]] = {}
    for r in city_recs:
        name = r.get("station") or r.get("station_name") or "UNKNOWN"
        st = stations.setdefault(
            name,
            {"pollutants": set(), "last_updates": [], "lat": None, "lon": None},
        )
        pol = r.get("pollutant_id") or r.get("pollutant") or r.get("parameter")
        if pol:
            st["pollutants"].add(str(pol))
        lu = _parse_last_update(str(r.get("last_update", "")))
        if lu:
            st["last_updates"].append(lu)
        for latk in ("latitude", "lat"):
            if r.get(latk) not in (None, ""):
                try:
                    st["lat"] = float(r[latk])
                except (TypeError, ValueError):
                    pass
        for lonk in ("longitude", "lon", "long"):
            if r.get(lonk) not in (None, ""):
                try:
                    st["lon"] = float(r[lonk])
                except (TypeError, ValueError):
                    pass

    station_rows = []
    stale_count = 0
    with_coords = 0
    pm25_count = 0
    for name, st in sorted(stations.items()):
        latest = max(st["last_updates"]) if st["last_updates"] else None
        age_h = round((now - latest).total_seconds() / 3600, 1) if latest else None
        is_stale = age_h is None or age_h > STALE_HOURS
        if is_stale:
            stale_count += 1
        if st["lat"] is not None and st["lon"] is not None:
            with_coords += 1
        has_pm25 = any("2.5" in p for p in st["pollutants"])
        if has_pm25:
            pm25_count += 1
        station_rows.append(
            {
                "station": name,
                "pollutants": sorted(st["pollutants"]),
                "has_pm25": has_pm25,
                "latest_update": latest.isoformat() if latest else None,
                "age_hours": age_h,
                "stale": is_stale,
                "lat": st["lat"],
                "lon": st["lon"],
            }
        )

    return {
        "available": True,
        "total_india_records": len(records),
        "city_records": len(city_recs),
        "station_count": len(stations),
        "stations_with_coords": with_coords,
        "stations_with_pm25": pm25_count,
        "stale_count": stale_count,
        "stations": station_rows,
    }


# ---------------------------------------------------------------------------
# OpenAQ backfill probe
# ---------------------------------------------------------------------------
def audit_openaq(sample: int = 5) -> dict[str, Any]:
    try:
        locations = openaq.fetch_locations()
    except SystemExit as e:
        return {"available": False, "reason": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": f"{type(e).__name__}: {e}"}

    # Probe daily coverage for PM2.5 sensors on a sample of locations.
    coverage_samples = []
    probed = []
    for loc in locations:
        if len(probed) >= sample:
            break
        pm_sensor = None
        for s in loc.get("sensors", []):
            pname = str(s.get("parameter", {}).get("name", "")).lower()
            if pname in ("pm25", "pm2.5"):
                pm_sensor = s
                break
        if not pm_sensor:
            continue
        try:
            days = openaq.fetch_sensor_daily_coverage(pm_sensor["id"], days=30)
        except Exception as e:  # noqa: BLE001
            probed.append({"location": loc.get("name"), "error": f"{type(e).__name__}: {e}"})
            continue
        cov = round(len(days) / 30.0, 2)
        coverage_samples.append(cov)
        probed.append(
            {
                "location": loc.get("name"),
                "sensor_id": pm_sensor["id"],
                "days_with_data_of_30": len(days),
                "coverage": cov,
            }
        )

    return {
        "available": True,
        "location_count": len(locations),
        "mean_pm25_coverage_30d": (
            round(statistics.mean(coverage_samples), 2) if coverage_samples else None
        ),
        "probed": probed,
    }


# ---------------------------------------------------------------------------
# Verdict + report
# ---------------------------------------------------------------------------
def decide(cpcb_a: dict[str, Any], openaq_a: dict[str, Any]) -> tuple[str, list[str]]:
    notes: list[str] = []
    n = cpcb_a.get("station_count", 0) if cpcb_a.get("available") else 0

    if not cpcb_a.get("available"):
        notes.append(f"CPCB snapshot unavailable: {cpcb_a.get('reason')}")
    if not openaq_a.get("available"):
        notes.append(f"OpenAQ backfill unavailable: {openaq_a.get('reason')}")

    if n >= MIN_STATIONS_GO:
        station_verdict = "GO"
    elif n >= MIN_STATIONS_CAUTION:
        station_verdict = "CAUTION"
        notes.append(f"Only {n} stations — IDW will be sparse; add a distance-confidence layer.")
    else:
        station_verdict = "NO-GO"
        notes.append(f"Only {n} stations found — too sparse for ward interpolation.")

    hist = openaq_a.get("mean_pm25_coverage_30d")
    if hist is not None and hist >= MIN_HISTORY_COVERAGE:
        notes.append(f"OpenAQ 30d PM2.5 coverage ~{hist:.0%} — 90-day backfill viable.")
    elif hist is not None:
        notes.append(f"OpenAQ 30d PM2.5 coverage only ~{hist:.0%} — backfill will have gaps.")

    verdict = station_verdict
    if station_verdict == "GO" and (hist is None or hist < MIN_HISTORY_COVERAGE):
        verdict = "CAUTION"
    return verdict, notes


def render_markdown(cpcb_a: dict[str, Any], openaq_a: dict[str, Any], verdict: str, notes: list[str]) -> str:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# Phase 0 — Data De-risk Audit",
        "",
        f"_Generated: {ts} · City: {config.CITY_NAME}, {config.CITY_STATE}_",
        "",
        f"## Verdict: **{verdict}**",
        "",
        "### GO/NO-GO criteria",
        f"- Stations: GO ≥ {MIN_STATIONS_GO}, CAUTION ≥ {MIN_STATIONS_CAUTION}, else NO-GO",
        f"- Staleness threshold: > {STALE_HOURS}h since last update",
        f"- Backfill viable if OpenAQ 30-day PM2.5 coverage ≥ {MIN_HISTORY_COVERAGE:.0%}",
        "",
        "### Notes",
    ]
    lines += [f"- {x}" for x in notes] or ["- (none)"]

    lines += ["", "## CPCB live snapshot (data.gov.in)"]
    if cpcb_a.get("available"):
        lines += [
            f"- Total India records in snapshot: {cpcb_a['total_india_records']}",
            f"- Bengaluru station×pollutant records: {cpcb_a['city_records']}",
            f"- **Distinct stations: {cpcb_a['station_count']}**",
            f"- Stations with coordinates: {cpcb_a['stations_with_coords']}",
            f"- Stations reporting PM2.5: {cpcb_a['stations_with_pm25']}",
            f"- Stale stations (> {STALE_HOURS}h): {cpcb_a['stale_count']}",
            "",
            "| Station | PM2.5 | Age (h) | Stale | Lat | Lon | Pollutants |",
            "|---|---|---|---|---|---|---|",
        ]
        for s in cpcb_a["stations"]:
            lines.append(
                f"| {s['station']} | {'✓' if s['has_pm25'] else '—'} | "
                f"{s['age_hours'] if s['age_hours'] is not None else '?'} | "
                f"{'⚠' if s['stale'] else 'ok'} | "
                f"{s['lat'] if s['lat'] is not None else '—'} | "
                f"{s['lon'] if s['lon'] is not None else '—'} | "
                f"{', '.join(s['pollutants'])} |"
            )
    else:
        lines.append(f"- Unavailable: {cpcb_a.get('reason')}")

    lines += ["", "## OpenAQ historical backfill probe"]
    if openaq_a.get("available"):
        lines += [
            f"- Locations in Bengaluru bbox: {openaq_a['location_count']}",
            f"- Mean 30-day PM2.5 coverage (sampled): {openaq_a['mean_pm25_coverage_30d']}",
            "",
            "| Location | Sensor | Days w/ data (of 30) | Coverage |",
            "|---|---|---|---|",
        ]
        for p in openaq_a["probed"]:
            if "error" in p:
                lines.append(f"| {p['location']} | — | — | error: {p['error']} |")
            else:
                lines.append(
                    f"| {p['location']} | {p['sensor_id']} | "
                    f"{p['days_with_data_of_30']} | {p['coverage']} |"
                )
    else:
        lines.append(f"- Unavailable: {openaq_a.get('reason')}")

    lines += ["", "---", "_Re-run: `python ingest/phase0_audit.py`_", ""]
    return "\n".join(lines)


def main() -> None:
    print("Phase 0 audit — pulling CPCB snapshot and probing OpenAQ...")
    cpcb_a = audit_cpcb()
    openaq_a = audit_openaq()
    verdict, notes = decide(cpcb_a, openaq_a)

    result = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "city": config.CITY_NAME,
        "verdict": verdict,
        "notes": notes,
        "cpcb": cpcb_a,
        "openaq": openaq_a,
    }

    out_json = config.REPO_ROOT / "evaluation" / "results" / "phase0_audit.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    out_md = config.REPO_ROOT / "docs" / "PHASE0_AUDIT.md"
    out_md.write_text(render_markdown(cpcb_a, openaq_a, verdict, notes), encoding="utf-8")

    print(f"\nVERDICT: {verdict}")
    for note in notes:
        print(f"  - {note}")
    print(f"\nWrote {out_md.relative_to(config.REPO_ROOT)} and {out_json.relative_to(config.REPO_ROOT)}")


if __name__ == "__main__":
    main()
