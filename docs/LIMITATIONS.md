# LIMITATIONS — VAAYU (say these proactively in the pitch)

Honesty is a stated differentiator. This file tracks every known weakness and
its improvement path. Never hide a weak number; contextualise it here.

## Data
- **Sparse stations, and unevenly so across cities.** Grid surfaces are
  interpolated (IDW) from a handful of CPCB stations per city — Tier-1 metros
  have 5–40, some Tier-2 cities have 1–3. This is an approximation, not
  measurement, and confidence must visibly vary by city, not just show one
  global caveat. Every map view carries a distance-to-nearest-station
  confidence indicator.
- **CPCB feed is a live snapshot only.** data.gov.in exposes the latest hourly
  reading per station, not history.
- **No pre-existing deep historical archive.** OpenAQ was the original plan
  for 90-day backfill, but its v3 signup email verification has been
  unreliable to receive. WAQI (aqicn.org) replaces it as the secondary/
  cross-validation source, but WAQI's free API is also a current-reading feed,
  not a deep archive. **Consequence: there is no shortcut to instant 90-day
  history.** The backfill window accrues from VAAYU's own hourly ingest
  starting Phase 1 — the dataset gets deeper every day the pipeline runs, and
  model quality (esp. forecast horizon confidence) improves accordingly. This
  is stated in the pitch, not discovered by a judge.
- **Ward boundaries are the actual nationwide bottleneck, not station data.**
  CPCB's network is genuinely national, but clean municipal ward GeoJSONs are
  case-by-case per city. A city stays Tier A (grid mode) until its boundary
  file is validated in `data/wards/<city_id>.geojson` — see
  `evaluation/results/phase0_audit.json` → `ward_geojson` for current status.
  Never claim ward-level detail for a city whose file isn't validated.
- **Staleness.** Government feeds go stale/flat. The `sentinel` agent flags
  stations >3h stale; forecasts on stale stations are down-weighted.

## Model
- **Short history window.** Backfill depth grows from zero at Phase 1 start,
  so early-phase models see far less than 90 days. This under-represents
  seasonal (winter burning) regimes for a while. If we don't beat naive
  persistence meaningfully, we say so, with the fix path: longer history,
  seasonal data.
- **Per-station and per-city variance.** Some stations forecast poorly, and a
  newly onboarded city with only days of backfill will predict worse than
  Bengaluru with a longer history. We report per-station AND per-city metrics
  rather than a single flattering aggregate — a city with 2 weeks of data
  still benefits from the shared global model (CLAUDE.md §6.2) but is shown
  as weaker, honestly.

## Attribution
- **Heuristic, not source apportionment.** Attribution maps model feature
  importance to human-readable causes via rules (stagnation / traffic /
  burning). Labelled "likely drivers" in the UI — never presented as measured
  source apportionment.

_Add rows as new limitations surface during the build._
