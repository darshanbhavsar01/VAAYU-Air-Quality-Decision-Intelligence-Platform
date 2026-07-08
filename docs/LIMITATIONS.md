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

## Agents — Gemini free-tier quota (Phase 4)
- **Gemini free tier is tightly rate-limited.** `gemini-2.5-flash` is only
  **20 requests/day**; one advisory generation (7 cities × EN+HI+regional ≈ 20
  calls) exhausts it. Switched to `gemini-2.5-flash-lite` (larger free daily
  quota) but that too can hit its daily cap after repeated runs, and the API
  intermittently returns 503 (overload). Design consequences (all shipped):
  advisories **upsert + skip-existing** so partial runs accumulate coverage
  instead of wiping; a **daily** (not hourly) `vaani-daily` job regenerates them
  within quota; every call is logged to `agent_logs` for volume tracking.
- **Multilingual advisory generation is proven** (English, Hindi, Kannada,
  Bengali, Tamil, Telugu, Marathi all generated correctly and grounded in the
  forecast JSON). On a fresh daily quota window the table fills to full coverage
  automatically; a demo snapshot is cached in BigQuery either way (§3.5).
- **Weekly MP report** uses Gemini Pro (→Flash fallback); generated on the daily
  cadence for the highest-signal cities to stay within quota.

## Deployment finding — data.gov.in blocks datacenter IPs
- **CPCB live ingest fails from Cloud Run** (`RemoteDisconnected` — data.gov.in
  drops connections from GCP egress IPs, even with browser UA + retries). The
  hourly Cloud Run Job is built to tolerate this: the CPCB step is non-fatal, so
  the forecast surfaces (CAMS + weather driven — both reachable from Cloud Run)
  still refresh every hour. Consequence: the **live CPCB "current" readings and
  station-health freshness only update when ingest runs from a non-datacenter IP**
  (e.g. locally, or via a proxy/NAT). The forecast product — the core demo — is
  fully live in the cloud; the CPCB freshness layer is not. Fix paths: egress
  proxy / static-IP NAT, or a small non-GCP scheduled runner for CPCB only.
  This does not affect the demo (surfaces are CAMS-driven and pre-cached per §3.5).

## Model — Phase 2 findings (be upfront about these)
- **Training target is CAMS-modelled, not CPCB-measured.** CPCB has no
  historical API, so the 24h-breach models train on CAMS (ECMWF) reanalysis at
  station locations. It is in a separate table (`aqi_cams`) with a source label,
  never mixed with CPCB (`raw_aqi`). We cross-validate CAMS vs live CPCB as real
  data accrues, and will retrain on CPCB once enough history exists.
- **"Breach" = NAAQS 24h limit (60 µg/m³), not CPCB Poor (90).** At 90, clean
  southern cities (Bengaluru, Chennai) have ~zero events *genuinely* — so a 90
  target is degenerate there. 60 is India's legal safe limit and the pitch's
  literal "safe limit"; it is non-degenerate for every city. This is documented,
  not tuned to flatter (a commoner target makes persistence harder to beat).
- **Overall breach AUC-PR barely beats persistence (0.993 vs 0.991)** because
  always-breaching Delhi (99.5% positive) dominates the aggregate. We say this
  plainly. The model's real, honest value shows in three places, all reported in
  `docs/EVALUATION.md`: (a) **onset recall 0.81 vs persistence 0.00** on
  currently-safe hours that breach within 24h — the actionable advance-warning
  case; (b) **regressor MAE 25.2 vs 34.7 µg/m³**, better in every city; (c)
  Kolkata (the seasonal-swing city) AUC-PR +0.06 over persistence.
- **Some cities/metrics under-perform persistence** (Hyderabad, Bengaluru breach
  AUC-PR) — shown in the per-city table, not hidden.
- **Clean cities have no TEST-season breaches** (Chennai/Mumbai/Pune = 0% in the
  monsoon test window) → their breach AUC is n/a. That is the season's truth; the
  regressor still gives them an accurate hotspot map.
- **Weather is per-city-centroid** (Phase 1 simplification); station-level weather
  and OSM static features (road density/land-use) are not yet added — an
  improvement path, not a claim.

## Attribution
- **Heuristic, not source apportionment.** Attribution maps model feature
  importance to human-readable causes via rules (stagnation / traffic /
  burning). Labelled "likely drivers" in the UI — never presented as measured
  source apportionment.

_Add rows as new limitations surface during the build._
