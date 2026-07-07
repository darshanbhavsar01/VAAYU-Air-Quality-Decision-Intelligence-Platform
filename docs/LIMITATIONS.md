# LIMITATIONS — VAAYU (say these proactively in the pitch)

Honesty is a stated differentiator. This file tracks every known weakness and
its improvement path. Never hide a weak number; contextualise it here.

## Data
- **Sparse stations.** Ward surfaces are interpolated (IDW) from ~10–15 CPCB
  stations across 198 wards. This is an approximation, not measurement. Every
  map view must carry a distance-to-nearest-station confidence indicator.
- **CPCB feed is a live snapshot only.** data.gov.in exposes the latest hourly
  reading per station, not history. 90-day backfill comes from OpenAQ, which
  mirrors most (not necessarily all) CPCB CAAQMS stations — coverage gaps exist.
- **Staleness.** Government feeds go stale/flat. The `sentinel` agent flags
  stations >3h stale; forecasts on stale stations are down-weighted.

## Model
- **Short history window.** A 90-day backfill under-represents seasonal
  (winter burning) regimes. If we don't beat naive persistence meaningfully, we
  say so, with the fix path: longer history, seasonal data.
- **Per-station variance.** Some stations forecast poorly; we report per-station
  metrics rather than a single flattering aggregate.

## Attribution
- **Heuristic, not source apportionment.** Attribution maps model feature
  importance to human-readable causes via rules (stagnation / traffic /
  burning). Labelled "likely drivers" in the UI — never presented as measured
  source apportionment.

_Add rows as new limitations surface during the build._
