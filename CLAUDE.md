# CLAUDE.md — VAAYU

**Nationwide Air Quality Decision Intelligence Platform** (grid-level for any city, ward-level for a curated list)
Track 2 (Pollution Hotspot Detection) — Build with AI: Code for Communities (Hack2skill × GDG)

---

## 1. Mission

VAAYU turns sparse government air-quality station data into **city-level pollution hotspot maps with 24-hour spike forecasts, source attribution, and MP-actionable intervention reports** — with a city selector covering all Tier-1 metros and a growing list of Tier-2 cities, deployable on GCP free tier via CPCB's national CAAQMS network.

One-liner for judges: *"Not another AQI dashboard. VAAYU tells any MP's office, in any Indian city, which neighbourhoods will breach safe limits tomorrow, why, and what to do about it — using only existing public infrastructure and near-zero cloud cost."*

## 2. Hackathon context (read this before making any product decision)

- Problem statement submitted by a sitting Member of Parliament. Judges = MPs + industry experts. Finale is in-person in New Delhi.
- Winning solutions get **piloted in real constituencies/districts**. Every design decision must survive the question: *"Could this run in a district office next month?"*
- Judge psychology: MPs reward *deployability, cost, and evidence for action* over ML sophistication. Technical judges reward *honest validation*. Serve both: simple visible product, rigorous appendix.

### 2.1 Multi-city scope (nationwide, not just Bengaluru)

CPCB runs a **national** real-time network — an All India CAAQMS Portal and All India CAAQMS Data Repository with a stations list covering the whole country — so pulling data for any Indian city is a config change, not a new integration. Going nationwide is genuinely feasible. The actual constraint is **ward/municipal boundary data**, which is not uniformly available or clean across Indian cities. So VAAYU uses **two granularity tiers**:

- **Tier A — Grid mode (works for every city with a CPCB station, i.e. effectively all Tier-1 and most Tier-2 cities):** IDW interpolation onto a fixed-resolution lat/lon grid clipped to the city's bounding box. No ward boundary data required. This is the **default and nationwide guarantee** — pick any city with CPCB coverage, VAAYU produces a hotspot map and forecast for it.
- **Tier B — Ward mode (curated city list, upgrades Tier A):** where a clean municipal ward boundary GeoJSON is confirmed available (own scraping/download, not assumed), the grid is aggregated up to actual ward polygons for MP-legible reporting. Start with a **target list of ~15–20 cities** (see `config/cities.yaml`) — all Tier-1 metros plus Tier-2 cities where corporation ward data is verifiably obtainable (many via OSM `admin_level` boundaries or state GIS portals). This list grows over time; it is never a hard requirement for a city to appear in the product.

**Do not promise ward-level detail for a city until its boundary file is actually validated in the repo.** Grid mode is always the honest fallback — say so in the UI ("ward view unavailable for this city — showing grid view") rather than silently degrading quality.

**One model, not N models.** Train a single global BQML model with `city`/`station_id` and station static features (road density, land-use) as categorical/numeric inputs, rather than one model per city. This is both the technically correct choice (more training data per model, cities share atmospheric physics) and the budget-correct choice (one training run, not fifteen) — see §3.1.

## 3. Hard constraints (never violate)

1. **Budget: ₹500 total, hard cap, for the entire 14-day build.** GCP free-tier first, always. Any service that risks crossing into paid tier needs a written cost estimate in `docs/BUDGET.md` before use, and the running total must stay under ₹500. See §3.1 for the concrete service-by-service plan. If projected spend approaches ₹400, stop and re-scope rather than continue — do not wait until the cap is breached.
2.  Anything not in the build phases (§12) is out of scope. When in doubt, cut scope, not quality.
3. **Public data only.** No scraped-in-violation-of-ToS sources. CPCB via data.gov.in, OpenAQ, Open-Meteo, OSM — all fine.
4. **Honest metrics always.** Weak numbers get reported with context and an improvement path — never hidden, never cherry-picked. This is a stated differentiator in the pitch.
5. **Demo must not depend on live third-party APIs at pitch time.** Everything demo-critical runs from cached/pre-loaded BigQuery data with a live-refresh option.

### 3.1 Budget plan (₹500 cap — this is the real constraint, treat it as load-bearing)

| Service | Usage in this project | Expected cost | Notes |
|---|---|---|---|
| BigQuery storage | 90-day backfill × multiple cities, hourly ingest, grid+ward surfaces | ₹0 | CPCB station count nationwide is in the low hundreds, hourly — total data volume across even 10–15 cities stays well within the 10GB free tier |
| BigQuery queries | Ingest, interpolation, dashboard reads, across all onboarded cities | ₹0 | Stay within 1TB/month free tier; batch queries, avoid `SELECT *` on wide tables; multi-city adds rows, not query complexity |
| BQML training | ARIMA_PLUS per station (all cities) + **one global** boosted tree across all cities | **Watch this** | BQML training bills as query bytes processed. Training ONE global classifier/regressor across all cities (not one per city — see §2.1) keeps this to a single billing event per model type. Train on filtered, narrow feature views (not full raw tables). Train once per model per phase, not on every code run. Estimate bytes with `--dry_run` before every training query. |
| Cloud Run (API + jobs) | FastAPI backend, hourly ingest/interpolate jobs | ₹0–~₹50 | Free tier: 2M requests, 360k GB-seconds/month. Hourly jobs at this scale stay free; set min-instances=0 (no idle billing), concurrency defaults fine |
| Cloud Scheduler | Hourly triggers | ₹0 | First 3 jobs free |
| Gemini API (AI Studio, not Vertex) | Advisories + MP reports via ADK agents | **~₹100–200 estimate** | Use the free-tier AI Studio API key, not Vertex AI endpoints — this avoids Vertex's per-request infra overhead and any GCP billing for the model calls entirely. Gemini Flash for advisories (cheap/free-tier friendly), reserve Gemini Pro calls for final report generation only, not every test run. Cache/log responses so repeated dev runs don't re-call the API. |
| Firebase Hosting (optional) | Static frontend | ₹0 | Free tier covers this easily |
| Secret Manager | API keys | ₹0 | 6 active secret versions free |
| data.gov.in / OpenAQ / Open-Meteo / OSM | External data | ₹0 | All free public APIs, no GCP billing |
| **Buffer** | | **~₹250–300 unspent** | Reserve for BQML retraining iterations or unexpected overages — do not spend proactively |

**Rules that keep this real:**
- Enable GCP budget alerts at ₹100/₹250/₹400 on day 1, before any other work.
- Use `bq query --dry_run` before every BQML training/prediction query to see bytes billed; log it in `docs/BUDGET.md`.
- Gemini API calls go through the **AI Studio API key** (`generativelanguage.googleapis.com`), not `aiplatform.googleapis.com` (Vertex) — this keeps model usage off the GCP bill entirely and onto Gemini API's own free/low-cost tier. Never introduce a Vertex AI Gemini endpoint into this project.
- No GKE, no Dataflow, no Composer, no Pub/Sub, no Vertex AI custom training or endpoints — all of these have either no meaningful free tier or standing costs that eat the ₹500 fast.
- If backfill or training costs threaten the cap, cut scope (fewer stations, shorter backfill window) — never silently let spend run past ₹500.

## 4. Architecture

```
config/cities.yaml (city registry: name, bbox, CPCB station IDs, ward GeoJSON path or null)
      │
      ▼
Cloud Scheduler (hourly, loops over active cities)
      │
      ▼
Cloud Run Job: ingest ──► BigQuery (raw_aqi, raw_weather — city_id column on every row)
      │                         │
      │                         ▼
      │                  BQML: ONE global model (city/station as features)
      │                         │
      ▼                         ▼
Cloud Run Job: interpolate ─► BigQuery (city_grid_surface, ward_surface where available, forecasts)
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                  ▼
      ADK Agent: QA     ADK Agent: Forecast   ADK Agent: Advisory
      (feed health)     & Attribution         (reports, alerts)
                                │
                                ▼
                    Cloud Run: FastAPI backend (city param on every endpoint)
                                │
                                ▼
                    Frontend (city selector → Leaflet map + dashboard)
                    Firebase Hosting or same Cloud Run
```

**Services:** Cloud Run (jobs + API), Cloud Scheduler, BigQuery + BQML, **Gemini API via AI Studio key** (`generativelanguage.googleapis.com` — Flash for advisories, Pro for MP reports; NOT Vertex AI), ADK for agents (configured to call the Gemini API directly, not through Vertex), Firebase Hosting (optional). Secret Manager for the Gemini API key.

**Explicitly NOT used:** GKE, Dataflow, Composer, Pub/Sub (Scheduler→Run is enough at this scale), Vertex AI (endpoints, custom training, or Gemini-via-Vertex — use the AI Studio Gemini API instead to keep model calls off GCP billing and within budget). Do not introduce these.

## 5. Data sources

| Source | Content | Access | Risk & mitigation |
|---|---|---|---|
| CPCB CAAQMS via All India Data Repository / data.gov.in API | Hourly PM2.5, PM10, NO2, SO2, CO, O3, per station, **nationwide** | Free API key | Flaky/stale feeds → dedupe on (station, pollutant, ts); QA agent flags staleness per city; OpenAQ fallback. Station coverage is uneven — Tier-1 metros have 5–40 stations, some Tier-2 cities have 1–3. Log actual coverage per city in `config/cities.yaml`, don't assume. |
| OpenAQ v3 API | Same pollutants, overlapping stations, also nationwide | Free | Backup + cross-validation of CPCB values, per city |
| Open-Meteo | Hourly wind speed/dir, temp, RH, pressure, precipitation; 48h forecast, any lat/lon | Free, no key | Primary weather features for the model — trivially multi-city since it's a lat/lon API |
| OSM (Geofabrik extracts) | Road density, industrial land use, construction proxies; also `admin_level` ward-ish boundaries for many Indian cities | Free download | Static features per city, computed once at onboarding. Ward boundary quality varies by city — validate before adding to Tier B list |
| Municipal ward boundaries (GeoJSON) | Corporation wards, where available | State GIS portals, OSM, city open-data portals — **case by case per city** | This is the actual bottleneck for nationwide. Never fabricate or approximate a ward boundary — if not confirmed, city stays in Tier A (grid mode) |
| Sentinel-5P NO2 via Earth Engine | Satellite NO2 columns | Free (EE) | **STRETCH ONLY** — do not start before Phase 4 |

**Backfill target:** 90 days historical CPCB data for **all onboarded cities in `config/cities.yaml`**, prioritizing Bengaluru first (home turf, fastest to validate), then remaining Tier-1 metros, then Tier-2 list. Day 1–2 priority; forecast quality depends on it.

### 5.1 City onboarding process (repeatable, config-driven)
1. Add entry to `config/cities.yaml`: `city_id, name, state, bbox, cpcb_station_ids[], ward_geojson_path (nullable)`.
2. Run `scripts/onboard_city.py <city_id>` — validates CPCB stations return data, computes OSM static features for the bbox, backfills available history.
3. If a ward GeoJSON is supplied and validated (`scripts/validate_ward_geojson.py` — checks coverage of bbox, no gaps/overlaps), city is Tier B; otherwise Tier A.
4. No code changes required to add a city — this is the point of the architecture.

**Target city list for the hackathon (realistic within 14 days + ₹500):** Bengaluru (Tier B, primary demo city) + 4–5 more Tier-1 metros in Tier A at minimum (Delhi, Mumbai, Chennai, Kolkata, Hyderabad) + attempt Tier B for any of these where ward data is quickly found. Additional Tier-2 cities (Pune, Ahmedabad, Jaipur, Lucknow, Kochi, Indore, etc.) added opportunistically in Phase 6 if backfill and budget allow — **do not let chasing city count crowd out model quality on the primary demo city.**

## 6. ML design (BQML)

### 6.1 Spike definition (fixed, cite CPCB breakpoints)
PM2.5 sub-index categories: Good ≤30, Satisfactory 31–60, Moderate 61–90, Poor 91–120, Very Poor 121–250, Severe >250 µg/m³.
**Spike event** = within next 24h, station's max PM2.5 (a) enters Poor or worse, OR (b) rises ≥1 full category from current. Same logic applied to PM10 as secondary target.

### 6.2 Models (in build order — one global model per model-type, all cities)
1. **Baseline: `ARIMA_PLUS`** per station×pollutant, hourly, 24h horizon, run for every onboarded station regardless of city. Cheap, fast, gives a defensible floor. Keep in final comparison table, broken out by city.
2. **Primary: `BOOSTED_TREE_CLASSIFIER`** — target: spike within 24h (binary). **Single model trained across all cities' data together** (more rows, shared atmospheric physics, one training run = one billing event). Features: lags (1,3,6,12,24h), rolling means/max (6,24h), hour-of-day, day-of-week, month, wind speed/direction (current + forecast), temperature, RH, precipitation, station static features (road density, land-use class), **plus `city_id` and station-level features so the model can learn city-specific baselines** (e.g. Delhi's winter stubble-burning pattern vs Bengaluru's traffic-driven pattern). Handle class imbalance via `AUTO_CLASS_WEIGHTS=TRUE` (same scale_pos_weight logic as TRAVIS).
3. **Secondary: `BOOSTED_TREE_REGRESSOR`** — next-24h max PM2.5 value (drives the map's forecast layer), same global-model approach.

**Why one model, not N city-specific models:** (a) budget — one training run stays within the BQML cost estimate in §3.1, N models would multiply it; (b) statistically sounder with limited backfill per city — a new city with only 2 weeks of data still benefits from patterns learned in Bengaluru's 90 days; (c) simpler to maintain and explain to judges. Report per-city breakdowns of the *shared* model's accuracy in evaluation, not per-city separate models.

### 6.3 Evaluation protocol (non-negotiable)
- **Temporal split only** — train on days 1–70, validate 71–80, test 81–90. Never random split on time series.
- Report: AUC-PR (not just ROC — spikes are rare), F1 at chosen threshold, recall (missing a spike is worse than a false alarm — say this in the pitch), MAE for the regressor, **per-station variance**, and **per-city variance** (a city with 2 weeks of backfill will predict worse than Bengaluru with 90 days — show it, explain it, don't hide it).
- Compare all models against a naive persistence baseline ("tomorrow = today"). If we don't beat persistence meaningfully, we say so and explain why (short backfill window) with the improvement path (longer history, seasonal data).
- Store all eval outputs in `evaluation/results/` as versioned JSON + a rendered `EVALUATION.md`.

### 6.4 Spatial interpolation (two-tier, per §2.1)
- **Tier A (grid, every city):** IDW from station points → fixed-resolution grid (e.g. 1km cells) clipped to the city's `bbox` from `config/cities.yaml` → aggregate to BigQuery GEOGRAPHY grid cells. Python job on Cloud Run, runs hourly per active city after ingest.
- **Tier B (ward, curated cities only):** where `ward_geojson_path` is set and validated, aggregate the Tier A grid up to ward polygons via `ST_WITHIN`/`ST_INTERSECTS` for MP-legible reporting. Ward mode is additive on top of grid mode, never a replacement — grid data is what the forecast model actually runs on.
- **Honesty clause:** IDW from a handful of stations is an approximation, not measurement — more so in cities with fewer stations. Every map view carries a confidence indicator (distance-to-nearest-station), and **confidence should visibly vary by city** (e.g. Delhi's dense network vs a Tier-2 city with 2 stations). Document limitations in `docs/LIMITATIONS.md` and say it proactively in the pitch — pre-empt the sharp judge, especially about sparse-station Tier-2 cities.

### 6.5 Attribution ("why is this spike coming")
- Feature-importance extraction from the boosted tree (`ML.FEATURE_IMPORTANCE`) + rule layer mapping dominant features to human causes: low wind speed + high RH → *stagnation*; hour 8–11/18–21 + high road density → *traffic*; seasonal month flags → *episodic burning*. Output: top-2 causes with confidence, per ward, per forecast. This is heuristic — label it as such in the UI ("likely drivers"), never as measured source apportionment.

## 7. ADK agents (three, mirroring VARUNA)

1. **`sentinel` (ingestion QA):** monitors feed freshness per station **across all onboarded cities**, flags stale (>3h) or anomalous readings (z-score jump without weather cause), maintains a station-health table (with city_id) the UI reads. Runs post-ingest, per city.
2. **`oracle` (forecast & attribution):** orchestrates BQML prediction calls, assembles ward-or-grid forecast + attribution payloads **for the selected city**, answers natural-language analytical questions over BigQuery for the MP dashboard, scoped to `city_id` ("which 5 wards in Bengaluru had the most exceedance days this month?" / "compare Delhi and Mumbai this week"). Tool access: BigQuery read-only.
3. **`vaani` (advisory & reports):** generates (a) citizen advisories in English/Kannada/Hindi (+ relevant state language as cities are added) via Gemini Flash (AI Studio API) — plain language, health-action oriented, grounded ONLY in forecast JSON passed to it, scoped to city (no free recall — hallucination control); (b) weekly **per-city** MP hotspot report via Gemini Pro (AI Studio API): top wards/grid-cells, trends, attributed causes, suggested interventions, rendered to PDF/HTML.

**Agent rules:** every Gemini API call (via AI Studio key, `google-genai` SDK pointed at `generativelanguage.googleapis.com`) gets structured JSON context + explicit "answer only from provided data" system instruction. Log all prompts/responses to BigQuery for audit — this also lets you track call volume against the free/low-cost tier. No agent writes to raw tables. Reserve Gemini Pro calls for final report generation runs, not iterative dev testing — use cached/mocked responses while developing agent logic to conserve budget.

## 8. API surface (FastAPI on Cloud Run)

```
GET  /cities                             → list of onboarded cities + tier (grid/ward) + coverage stats
GET  /wards?city={city_id}                → GeoJSON with current AQI surface + confidence (ward or grid, per tier)
GET  /wards/{id}/forecast?city={city_id}  → 24h spike prob, predicted max, attribution
GET  /stations/health?city={city_id}      → sentinel output
GET  /reports/weekly?city={city_id}       → latest MP report (HTML/PDF)
POST /ask                                 → oracle agent NL query (city inferred from question or param)
GET  /advisories?city={city_id}&lang=kn|hi|en   → current citizen advisories
```

## 9. Frontend (keep deliberately thin)

Single-page app: **city selector dropdown at the top** (drives every subsequent call), Leaflet map (ward choropleth for Tier B cities, grid heatmap for Tier A — visually distinguish the two so it's clear which mode is active), current + toggle to "tomorrow" forecast layer, click-a-cell/ward panel (forecast, attribution, advisory), station health strip, and an "Ask VAAYU" chat box hitting `/ask`. MP report accessible as a rendered page + download, per city. No auth, no user accounts, no mobile app. Vanilla JS or minimal React — whatever ships fastest.

## 10. Repo structure

```
vaayu/
├── CLAUDE.md                  # this file
├── config/cities.yaml         # city registry: bbox, stations, ward geojson path
├── docs/{BUDGET,LIMITATIONS,EVALUATION,PITCH}.md
├── scripts/{onboard_city.py,validate_ward_geojson.py}
├── ingest/                    # Cloud Run jobs: cpcb, openaq, weather, interpolate (all city-parameterized)
├── ml/                        # BQML DDL/SQL, feature views, eval queries (global model, city_id feature)
├── agents/{sentinel,oracle,vaani}/
├── api/                       # FastAPI app
├── web/                       # frontend (city selector)
├── infra/                     # deploy scripts, scheduler config, IAM notes
└── evaluation/results/
```

## 11. Working conventions for Claude Code

- Python 3.11+, FastAPI, `uv` or pip-tools lockfile. Type hints everywhere. `ruff` clean.
- All SQL in versioned `.sql` files under `ml/` — never inline in Python.
- Every ingest job idempotent (MERGE, not INSERT). Re-running must never duplicate rows.
- Config via env vars; Gemini AI Studio API key + other secrets via Secret Manager; nothing sensitive in repo.
- Every BQML training/prediction query gets a `--dry_run` cost check first; log bytes billed in `docs/BUDGET.md`.
- Each phase ends with a working deployed increment — no big-bang integration.
- When a metric is bad, write it down as-is and open a "why + fix path" note. Do not tune thresholds to flatter the demo.

## 12. Build phases (14 days)

| Phase | Days | Deliverable (deployed & working) |
|---|---|---|
| 0. De-risk | 0.5 | Pull 30 days CPCB data for Bengaluru + spot-check 4 other Tier-1 metros' station availability. Audit ward GeoJSON availability for the target city list. **GO/NO-GO on data quality + realistic Tier B city count.** |
| 1. Pipeline | 1–3 | City registry (`config/cities.yaml`) live; hourly ingest working for Bengaluru; 90-day backfill for Bengaluru; onboarding script tested on 1 more city |
| 2. Models | 4–6 | ARIMA_PLUS + global boosted tree trained across onboarded cities; temporal-split eval (incl. per-city breakdown) written to EVALUATION.md |
| 3. Spatial + API + multi-city rollout | 7–9 | Grid interpolation working for all Tier-1 metros in registry; ward aggregation for Bengaluru (+ any other validated cities); FastAPI endpoints city-parameterized; map renders with city selector |
| 4. Agents | 10–11 | sentinel + oracle + vaani deployed, all city-aware; advisories in 3 languages; /ask works across cities |
| 5. Reports + pitch | 12–13 | Weekly MP report generator (per city); demo script showing 2–3 different cities live; 3-min video; BUDGET.md finalized |
| 6. Buffer / stretch cities | 14 | Cached demo data snapshots for all demo cities; opportunistically onboard 1–2 Tier-2 cities if budget/time allow; submission polish |

## 13. Demo narrative (finale)

1. Open on the MP's pain: complaints about air, no ward-level evidence to act — **for their specific constituency, wherever it is in India.**
2. **Pick Bengaluru from the city selector** → today's map → click a ward → **tomorrow's spike forecast + why** (attribution).
3. **Validation moment:** show yesterday's forecast vs today's actuals. Honest metrics slide (incl. per-station and per-city weakness).
4. **Switch the city selector to Delhi or another onboarded city live** — same platform, same models, no redeploy — this is the single most persuasive nationwide moment in the demo.
5. Show the weekly MP report — "this lands in your office every Monday, for your constituency."
6. Cost slide: total build cost under ₹500 (near-zero ongoing) **across all onboarded cities**, zero new hardware, existing CPCB infra, Gemini API on free/low-cost tier rather than enterprise Vertex AI infra.
7. Scale slide: config-driven city onboarding (one YAML entry + optional ward file = new city), grid mode as the nationwide guarantee, ward mode as a growing curated layer on top.

## 14. Non-goals (do not build)

- No IoT/sensor hardware proposals. No mobile app. No user accounts/auth. No source apportionment claims beyond the labeled heuristic. No paid data. No Pub/Sub/Dataflow/GKE. No Vertex AI (endpoints, custom training, or Gemini-via-Vertex) — use the AI Studio Gemini API only. No real-time streaming — hourly is the product decision, defend it. No spend past ₹500 — re-scope before that happens, don't discover it after. **No claiming ward-level detail for a city whose boundary file isn't validated in the repo — grid mode is the honest default, say so in the UI.** No per-city custom BQML models — one global model, per §2.1.

## 15. Stretch (only if Phase 5 done early)

Onboard additional Tier-2 cities beyond the core list (Pune, Ahmedabad, Jaipur, Lucknow, Kochi, Indore, etc. — whichever have quick-to-validate ward data or are fine staying in grid mode). Citizen photo-report layer (burning/dust/traffic) feeding attribution — the Track 1 hybrid. Sentinel-5P NO2 overlay. Kannada/Hindi voice advisory via TTS. Cross-city comparison view on the dashboard ("compare my constituency to similar-sized cities").

## Git Commit Guidelines
- Do not include AI attribution or co-author lines in commit messages.