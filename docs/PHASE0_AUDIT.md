# Phase 0 — Data De-risk Audit (nationwide/multi-city)

_Generated: 2026-07-07T19:09:47+00:00_

## Verdict: **GO**

### GO/NO-GO criteria (primary demo city: Bengaluru)
- Stations: GO ≥ 8, CAUTION ≥ 5, else NO-GO
- Staleness threshold: > 3h since last update
- Secondary Tier-1 cities spot-checked at a lower bar (≥ 2 stations = usable signal)

### Notes
- Tier B readiness: 0/6 cities have a validated ward GeoJSON today — every city ships Tier A (grid) now. Sourcing Bengaluru's ward boundary is the Phase 1 priority per CLAUDE.md §5.1; grid mode is the honest default.
- Reminder: neither CPCB (live snapshot only) nor WAQI (current-reading API) gives pre-existing deep history — 90-day backfill accrues from VAAYU's own hourly ingest starting Phase 1, not from a one-shot pull. State this in the pitch (docs/LIMITATIONS.md).

## CPCB per-city station audit
- Total India records in one national snapshot: 3430

| City | Stations | With PM2.5 | Stale (>3h) |
|---|---|---|---|
| Bengaluru | 10 | 10 | 0 |
| Delhi | 45 | 45 | 0 |
| Mumbai | 23 | 23 | 0 |
| Chennai | 7 | 7 | 0 |
| Kolkata | 7 | 7 | 0 |
| Hyderabad | 13 | 13 | 0 |

### Bengaluru station detail
| Station | PM2.5 | Age (h) | Stale | Pollutants |
|---|---|---|---|---|
| BTM Layout, Bengaluru - CPCB | ✓ | 0.7 | ok | CO, NH3, NO2, OZONE, PM10, PM2.5, SO2 |
| BWSSB Kadabesanahalli, Bengaluru - CPCB | ✓ | 0.7 | ok | CO, NH3, NO2, OZONE, PM10, PM2.5, SO2 |
| Bapuji Nagar, Bengaluru - KSPCB | ✓ | 0.7 | ok | CO, NH3, NO2, OZONE, PM10, PM2.5, SO2 |
| City Railway Station, Bengaluru - KSPCB | ✓ | 0.7 | ok | CO, NH3, NO2, OZONE, PM10, PM2.5, SO2 |
| Hebbal, Bengaluru - KSPCB | ✓ | 0.7 | ok | CO, NH3, NO2, OZONE, PM10, PM2.5, SO2 |
| Hombegowda Nagar, Bengaluru - KSPCB | ✓ | 0.7 | ok | CO, NH3, NO2, OZONE, PM10, PM2.5, SO2 |
| Jayanagar 5th Block, Bengaluru - KSPCB | ✓ | 0.7 | ok | CO, NH3, NO2, OZONE, PM10, PM2.5, SO2 |
| Jigani, Bengaluru - KSPCB | ✓ | 0.7 | ok | CO, NH3, NO2, OZONE, PM10, PM2.5, SO2 |
| Kasturi Nagar, Bengaluru - KSPCB | ✓ | 0.7 | ok | CO, NH3, NO2, OZONE, PM10, PM2.5, SO2 |
| Silk Board, Bengaluru - KSPCB | ✓ | 0.7 | ok | CO, NH3, NO2, OZONE, PM10, PM2.5, SO2 |

## WAQI cross-check (independent live-AQI sanity signal per city)

_WAQI free tier serves only the named-city feed reliably; its bounds/geo endpoints are restricted, so this is a coarse corroboration, not a station inventory. Units differ from CPCB (US-AQI index vs µg/m³) — do not compare numerically. See docs/LIMITATIONS.md._

| City | WAQI resolved station | Dominant AQI | PM2.5 sub-index |
|---|---|---|---|
| Bengaluru | Hombegowda Nagar, Bengaluru, India | 53 | 53 |
| Delhi | Major Dhyan Chand National Stadium, Delhi, Delhi, India | 82 | 82 |
| Mumbai | Mumbai US Consulate, India (मुंबई अमेरिकी वाणिज्य दूतावास) | 158 | 158 |
| Chennai | Chennai US Consulate, Chennai, India (चेन्नई अमेरिकी वाणिज्य दूतावास) | 46 | 46 |
| Kolkata | Kolkata US Consulate, India (कोलकाता अमेरिकी वाणिज्य दूतावास) | 172 | 172 |
| Hyderabad | Hyderabad US Consulate, India (हैदराबाद अमेरिकी वाणिज्य दूतावास) | 93 | 93 |

## Ward GeoJSON audit (Tier B eligibility)
- Validated Tier B cities: 0 / 6

| City | Registry tier | GeoJSON found | Path checked |
|---|---|---|---|
| Bengaluru | A | — | `data\wards\bengaluru.geojson` |
| Delhi | A | — | `data\wards\delhi.geojson` |
| Mumbai | A | — | `data\wards\mumbai.geojson` |
| Chennai | A | — | `data\wards\chennai.geojson` |
| Kolkata | A | — | `data\wards\kolkata.geojson` |
| Hyderabad | A | — | `data\wards\hyderabad.geojson` |

---
_Re-run: `python ingest/phase0_audit.py`_
