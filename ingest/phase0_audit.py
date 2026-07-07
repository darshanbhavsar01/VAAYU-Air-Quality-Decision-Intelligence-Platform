"""Phase 0 — De-risk (nationwide/multi-city version, CLAUDE.md §12 Phase 0).

Deliverable: pull CPCB data for Bengaluru (primary demo city, full audit) +
spot-check station availability for the other Tier-1 metros in
config/cities.yaml, and audit ward GeoJSON availability for the target city
list. Produces a GO/CAUTION/NO-GO verdict plus a realistic Tier B (ward-mode)
city count.

Sources:
  - CPCB live snapshot (data.gov.in): station count, pollutants, staleness,
    per city, from ONE national fetch (§5: it's genuinely one API, filtered
    per city — not one integration per city).
  - WAQI (aqicn.org): secondary/cross-validation station count per city, via
    map/bounds. Replaces OpenAQ (email verification has been unreliable) —
    see ingest/waqi.py docstring for why this does not give deep history.
  - Ward GeoJSON: checked against data/wards/<city_id>.geojson; none exist
    yet in this repo, so every city currently reports Tier A (grid only).

Run: python ingest/phase0_audit.py
Each source is independent — a missing key for one still lets others run.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import config
import cpcb
import waqi
from cities import City, load_cities

# --- GO/NO-GO thresholds for the PRIMARY demo city (Bengaluru) ---
MIN_STATIONS_GO = 8          # fewer than this and IDW interpolation is too sparse
MIN_STATIONS_CAUTION = 5
STALE_HOURS = 3              # CLAUDE.md sentinel definition of "stale"

# Spot-check bar for secondary Tier-1 cities — lower bar, just "is there a signal at all"
MIN_STATIONS_SPOTCHECK = 2


# ---------------------------------------------------------------------------
# CPCB per-city audit
# ---------------------------------------------------------------------------
def audit_city_cpcb(city: City, records: list[dict[str, Any]]) -> dict[str, Any]:
    city_recs = cpcb.filter_city(records, city.name, city.state)
    now = datetime.now(timezone.utc)

    stations: dict[str, dict[str, Any]] = {}
    for r in city_recs:
        name = r.get("station") or r.get("station_name") or "UNKNOWN"
        st = stations.setdefault(name, {"pollutants": set(), "last_updates": []})
        pol = r.get("pollutant_id") or r.get("pollutant") or r.get("parameter")
        if pol:
            st["pollutants"].add(str(pol))
        lu = cpcb.parse_cpcb_timestamp(str(r.get("last_update", "")))
        if lu:
            st["last_updates"].append(lu)

    station_rows = []
    stale_count = 0
    pm25_count = 0
    for name, st in sorted(stations.items()):
        latest = max(st["last_updates"]) if st["last_updates"] else None
        age_h = round((now - latest).total_seconds() / 3600, 1) if latest else None
        is_stale = age_h is None or age_h > STALE_HOURS
        if is_stale:
            stale_count += 1
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
            }
        )

    return {
        "city_id": city.city_id,
        "city_name": city.name,
        "city_records": len(city_recs),
        "station_count": len(stations),
        "stations_with_pm25": pm25_count,
        "stale_count": stale_count,
        "stations": station_rows,
    }


def audit_all_cities_cpcb() -> dict[str, Any]:
    try:
        records = cpcb.fetch_cpcb_snapshot()
    except SystemExit as e:
        return {"available": False, "reason": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": f"{type(e).__name__}: {e}"}

    per_city = [audit_city_cpcb(c, records) for c in load_cities()]
    return {"available": True, "total_india_records": len(records), "cities": per_city}


# ---------------------------------------------------------------------------
# WAQI cross-check (coarse independent sanity signal per city)
# ---------------------------------------------------------------------------
def audit_waqi() -> dict[str, Any]:
    """Independent live-AQI sanity check per city via WAQI's named-city feed.

    NOT a station inventory — WAQI's free-tier bounds/geo endpoints are
    unreliable (see ingest/waqi.py). This only corroborates that an outside
    source reports a live reading for the city.
    """
    per_city = []
    any_ok = False
    last_error = None
    for c in load_cities():
        result = None
        for candidate in (c.city_id, c.name.lower()):
            try:
                result = waqi.city_crosscheck(candidate)
                any_ok = True
                break
            except Exception as e:  # noqa: BLE001
                last_error = f"{type(e).__name__}: {e}"
        if result is not None:
            per_city.append({"city_id": c.city_id, "city_name": c.name, **result})
        else:
            per_city.append({"city_id": c.city_id, "city_name": c.name, "error": last_error})
    return {"available": any_ok, "reason": None if any_ok else last_error, "cities": per_city}


# ---------------------------------------------------------------------------
# Ward GeoJSON audit
# ---------------------------------------------------------------------------
def audit_ward_geojson() -> dict[str, Any]:
    wards_dir = config.DATA_DIR / "wards"
    rows = []
    validated_count = 0
    for c in load_cities():
        expected = wards_dir / f"{c.city_id}.geojson"
        exists = expected.exists()
        if exists:
            validated_count += 1
        rows.append(
            {
                "city_id": c.city_id,
                "city_name": c.name,
                "registry_tier": c.tier,
                "geojson_found": exists,
                "path_checked": str(expected.relative_to(config.REPO_ROOT)),
            }
        )
    return {"validated_tier_b_count": validated_count, "cities": rows}


# ---------------------------------------------------------------------------
# Verdict + report
# ---------------------------------------------------------------------------
def decide(
    cpcb_a: dict[str, Any], waqi_a: dict[str, Any], ward_a: dict[str, Any]
) -> tuple[str, list[str]]:
    notes: list[str] = []

    if not cpcb_a.get("available"):
        notes.append(f"CPCB snapshot unavailable: {cpcb_a.get('reason')}")
        return "NO-GO", notes
    if not waqi_a.get("available"):
        notes.append(f"WAQI cross-check unavailable: {waqi_a.get('reason')} (non-blocking, secondary source only)")

    primary = next((c for c in cpcb_a["cities"] if c["city_id"] == "bengaluru"), None)
    if primary is None:
        return "NO-GO", ["Primary city 'bengaluru' missing from cities.yaml results."]

    n = primary["station_count"]
    if n >= MIN_STATIONS_GO:
        verdict = "GO"
    elif n >= MIN_STATIONS_CAUTION:
        verdict = "CAUTION"
        notes.append(f"Bengaluru: only {n} CPCB stations — IDW will be sparse; ship a visible confidence layer.")
    else:
        verdict = "NO-GO"
        notes.append(f"Bengaluru: only {n} CPCB stations — too sparse for the primary demo city.")

    weak_spotchecks = [
        c["city_name"] for c in cpcb_a["cities"]
        if c["city_id"] != "bengaluru" and c["station_count"] < MIN_STATIONS_SPOTCHECK
    ]
    if weak_spotchecks:
        notes.append(
            f"Spot-check below {MIN_STATIONS_SPOTCHECK} stations: {', '.join(weak_spotchecks)} — "
            f"keep these Tier A (grid) only, do not promise ward view."
        )

    # Ward GeoJSON absence is EXPECTED at Phase 0 — it's Phase 1 sourcing work,
    # not a data-quality risk. Report it as a separate dimension (Tier B
    # readiness), never as a downgrade of the data-quality verdict, or the
    # headline misleadingly signals a risk that doesn't exist.
    notes.append(
        f"Tier B readiness: {ward_a['validated_tier_b_count']}/{len(ward_a['cities'])} cities have a "
        "validated ward GeoJSON today — every city ships Tier A (grid) now. Sourcing Bengaluru's "
        "ward boundary is the Phase 1 priority per CLAUDE.md §5.1; grid mode is the honest default."
    )

    notes.append(
        "Reminder: neither CPCB (live snapshot only) nor WAQI (current-reading API) gives "
        "pre-existing deep history — 90-day backfill accrues from VAAYU's own hourly ingest "
        "starting Phase 1, not from a one-shot pull. State this in the pitch (docs/LIMITATIONS.md)."
    )

    return verdict, notes


def render_markdown(
    cpcb_a: dict[str, Any], waqi_a: dict[str, Any], ward_a: dict[str, Any],
    verdict: str, notes: list[str],
) -> str:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# Phase 0 — Data De-risk Audit (nationwide/multi-city)",
        "",
        f"_Generated: {ts}_",
        "",
        f"## Verdict: **{verdict}**",
        "",
        "### GO/NO-GO criteria (primary demo city: Bengaluru)",
        f"- Stations: GO ≥ {MIN_STATIONS_GO}, CAUTION ≥ {MIN_STATIONS_CAUTION}, else NO-GO",
        f"- Staleness threshold: > {STALE_HOURS}h since last update",
        f"- Secondary Tier-1 cities spot-checked at a lower bar (≥ {MIN_STATIONS_SPOTCHECK} stations = usable signal)",
        "",
        "### Notes",
    ]
    lines += [f"- {x}" for x in notes] or ["- (none)"]

    lines += ["", "## CPCB per-city station audit"]
    if cpcb_a.get("available"):
        lines += [
            f"- Total India records in one national snapshot: {cpcb_a['total_india_records']}",
            "",
            "| City | Stations | With PM2.5 | Stale (>3h) |",
            "|---|---|---|---|",
        ]
        for c in cpcb_a["cities"]:
            lines.append(
                f"| {c['city_name']} | {c['station_count']} | {c['stations_with_pm25']} | {c['stale_count']} |"
            )
        primary = next((c for c in cpcb_a["cities"] if c["city_id"] == "bengaluru"), None)
        if primary:
            lines += [
                "",
                "### Bengaluru station detail",
                "| Station | PM2.5 | Age (h) | Stale | Pollutants |",
                "|---|---|---|---|---|",
            ]
            for s in primary["stations"]:
                lines.append(
                    f"| {s['station']} | {'✓' if s['has_pm25'] else '—'} | "
                    f"{s['age_hours'] if s['age_hours'] is not None else '?'} | "
                    f"{'⚠' if s['stale'] else 'ok'} | {', '.join(s['pollutants'])} |"
                )
    else:
        lines.append(f"- Unavailable: {cpcb_a.get('reason')}")

    lines += [
        "",
        "## WAQI cross-check (independent live-AQI sanity signal per city)",
        "",
        "_WAQI free tier serves only the named-city feed reliably; its bounds/geo "
        "endpoints are restricted, so this is a coarse corroboration, not a station "
        "inventory. Units differ from CPCB (US-AQI index vs µg/m³) — do not compare "
        "numerically. See docs/LIMITATIONS.md._",
        "",
    ]
    if waqi_a.get("available"):
        lines += [
            "| City | WAQI resolved station | Dominant AQI | PM2.5 sub-index |",
            "|---|---|---|---|",
        ]
        for c in waqi_a["cities"]:
            if "error" in c:
                lines.append(f"| {c['city_name']} | error: {c['error']} | — | — |")
            else:
                lines.append(
                    f"| {c['city_name']} | {c.get('resolved_station', '—')} | "
                    f"{c.get('dominant_aqi', '—')} | {c.get('pm25_subindex', '—')} |"
                )
    else:
        lines.append(f"- Unavailable: {waqi_a.get('reason')}")

    lines += ["", "## Ward GeoJSON audit (Tier B eligibility)"]
    lines += [
        f"- Validated Tier B cities: {ward_a['validated_tier_b_count']} / {len(ward_a['cities'])}",
        "",
        "| City | Registry tier | GeoJSON found | Path checked |",
        "|---|---|---|---|",
    ]
    for c in ward_a["cities"]:
        lines.append(
            f"| {c['city_name']} | {c['registry_tier']} | "
            f"{'✓' if c['geojson_found'] else '—'} | `{c['path_checked']}` |"
        )

    lines += ["", "---", "_Re-run: `python ingest/phase0_audit.py`_", ""]
    return "\n".join(lines)


def main() -> None:
    print("Phase 0 audit — CPCB nationwide snapshot, WAQI cross-check, ward GeoJSON audit...")
    cpcb_a = audit_all_cities_cpcb()
    waqi_a = audit_waqi()
    ward_a = audit_ward_geojson()
    verdict, notes = decide(cpcb_a, waqi_a, ward_a)

    result = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "notes": notes,
        "cpcb": cpcb_a,
        "waqi": waqi_a,
        "ward_geojson": ward_a,
    }

    out_json = config.REPO_ROOT / "evaluation" / "results" / "phase0_audit.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    out_md = config.REPO_ROOT / "docs" / "PHASE0_AUDIT.md"
    out_md.write_text(render_markdown(cpcb_a, waqi_a, ward_a, verdict, notes), encoding="utf-8")

    print(f"\nVERDICT: {verdict}")
    for note in notes:
        print(f"  - {note}")
    print(f"\nWrote {out_md.relative_to(config.REPO_ROOT)} and {out_json.relative_to(config.REPO_ROOT)}")


if __name__ == "__main__":
    main()
