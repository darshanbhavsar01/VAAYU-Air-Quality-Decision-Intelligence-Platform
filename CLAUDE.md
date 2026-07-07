# CLAUDE.md — VAAYU

**Ward-Level Air Quality Decision Intelligence Platform**
Track 2 (Pollution Hotspot Detection) — Build with AI: Code for Communities (Hack2skill × GDG)

---

## 1. Mission

VAAYU turns sparse government air-quality station data into **ward-level pollution hotspot maps with 24-hour spike forecasts, source attribution, and MP-actionable intervention reports** for Bengaluru — deployable on GCP free tier, scalable to any Indian city with CPCB coverage.

One-liner for judges: *"Not another AQI dashboard. VAAYU tells the MP's office which neighbourhoods will breach safe limits tomorrow, why, and what to do about it — using only existing public infrastructure and near-zero cloud cost."*

## 2. Hackathon context (read this before making any product decision)

- Problem statement submitted by a sitting Member of Parliament. Judges = MPs + industry experts. Finale is in-person in New Delhi.
- Winning solutions get **piloted in real constituencies/districts**. Every design decision must survive the question: *"Could this run in a district office next month?"*
- Judge psychology: MPs reward *deployability, cost, and evidence for action* over ML sophistication. Technical judges reward *honest validation*. Serve both: simple visible product, rigorous appendix.

## 3. Hard constraints (never violate)

1. **Budget: ₹500 total, hard cap, for the entire 14-day build.** GCP free-tier first, always. Any service that risks crossing into paid tier needs a written cost estimate in `docs/BUDGET.md` before use, and the running total must stay under ₹500. See §3.1 for the concrete service-by-service plan. If projected spend approaches ₹400, stop and re-scope rather than continue — do not wait until the cap is breached.
2. Anything not in the build phases (§12) is out of scope. When in doubt, cut scope, not quality.
3. **Public data only.** No scraped-in-violation-of-ToS sources. CPCB via data.gov.in, OpenAQ, Open-Meteo, OSM — all fine.
4. **Honest metrics always.** Weak numbers get reported with context and an improvement path — never hidden, never cherry-picked. This is a stated differentiator in the pitch.
5. **Demo must not depend on live third-party APIs at pitch time.** Everything demo-critical runs from cached/pre-loaded BigQuery data with a live-refresh option.

### 3.1 Budget plan (₹500 cap — this is the real constraint, treat it as load-bearing)

| Service | Usage in this project | Expected cost | Notes |
|---|---|---|---|
| BigQuery storage | 90-day backfill, hourly ingest, ward surfaces | ₹0 | Well within 10GB free tier |
| BigQuery queries | Ingest, interpolation, dashboard reads | ₹0 | Stay within 1TB/month free tier; batch queries, avoid `SELECT *` on wide tables |
| BQML training | ARIMA_PLUS + boosted tree, per station×pollutant | **Watch this** | BQML training bills as query bytes processed. Train on filtered, narrow feature views (not full raw tables). Train once per model per phase, not on every code run. Estimate bytes with `--dry_run` before every training query. |
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
Cloud Scheduler (hourly)
      │
      ▼
Cloud Run Job: ingest ──► BigQuery (raw_aqi, raw_weather)
      │                         │
      │                         ▼
      │                  BQML models (spike forecast)
      │                         │
      ▼                         ▼
Cloud Run Job: interpolate ─► BigQuery (ward_surface, forecasts)
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                  ▼
      ADK Agent: QA     ADK Agent: Forecast   ADK Agent: Advisory
      (feed health)     & Attribution         (reports, alerts)
                                │
                                ▼
                    Cloud Run: FastAPI backend
                                │
                                ▼
                    Frontend (Leaflet map + dashboard)
                    Firebase Hosting or same Cloud Run
```

**Services:** Cloud Run (jobs + API), Cloud Scheduler, BigQuery + BQML, **Gemini API via AI Studio key** (`generativelanguage.googleapis.com` — Flash for advisories, Pro for MP reports; NOT Vertex AI), ADK for agents (configured to call the Gemini API directly, not through Vertex), Firebase Hosting (optional). Secret Manager for the Gemini API key.

**Explicitly NOT used:** GKE, Dataflow, Composer, Pub/Sub (Scheduler→Run is enough at this scale), Vertex AI (endpoints, custom training, or Gemini-via-Vertex — use the AI Studio Gemini API instead to keep model calls off GCP billing and within budget). Do not introduce these.

## 5. Data sources

| Source | Content | Access | Risk & mitigation |
|---|---|---|---|
| CPCB CAAQMS via data.gov.in API | Hourly PM2.5, PM10, NO2, SO2, CO, O3 per station | Free API key | Flaky/stale feeds → dedupe on (station, pollutant, ts); QA agent flags staleness; OpenAQ fallback |
| OpenAQ v3 API | Same pollutants, overlapping stations | Free | Backup + cross-validation of CPCB values |
| Open-Meteo | Hourly wind speed/dir, temp, RH, pressure, precipitation; 48h forecast | Free, no key | Primary weather features for the model |
| OSM (Geofabrik extract) | Road density, industrial land use, construction proxies per ward | Free download | Static features, computed once |
| BBMP ward boundaries (GeoJSON) | 198 (or current) Bengaluru wards | Public GIS portals | Load once into BigQuery GEOGRAPHY |
| Sentinel-5P NO2 via Earth Engine | Satellite NO2 columns | Free (EE) | **STRETCH ONLY** — do not start before Phase 4 |

**Backfill target:** 90 days historical CPCB data for all Bengaluru stations (day 1–2 priority; forecast quality depends on it).

## 6. ML design (BQML)

### 6.1 Spike definition (fixed, cite CPCB breakpoints)
PM2.5 sub-index categories: Good ≤30, Satisfactory 31–60, Moderate 61–90, Poor 91–120, Very Poor 121–250, Severe >250 µg/m³.
**Spike event** = within next 24h, station's max PM2.5 (a) enters Poor or worse, OR (b) rises ≥1 full category from current. Same logic applied to PM10 as secondary target.

### 6.2 Models (in build order)
1. **Baseline: `ARIMA_PLUS`** per station×pollutant, hourly, 24h horizon. Cheap, fast, gives a defensible floor. Keep in final comparison table.
2. **Primary: `BOOSTED_TREE_CLASSIFIER`** — target: spike within 24h (binary). Features: lags (1,3,6,12,24h), rolling means/max (6,24h), hour-of-day, day-of-week, month, wind speed/direction (current + forecast), temperature, RH, precipitation, station static features (road density, land-use class). Handle class imbalance via `AUTO_CLASS_WEIGHTS=TRUE` (same scale_pos_weight logic as TRAVIS).
3. **Secondary: `BOOSTED_TREE_REGRESSOR`** — next-24h max PM2.5 value (drives the map's forecast layer).

### 6.3 Evaluation protocol (non-negotiable)
- **Temporal split only** — train on days 1–70, validate 71–80, test 81–90. Never random split on time series.
- Report: AUC-PR (not just ROC — spikes are rare), F1 at chosen threshold, recall (missing a spike is worse than a false alarm — say this in the pitch), MAE for the regressor, and **per-station variance** (some stations will predict badly; show it).
- Compare all models against a naive persistence baseline ("tomorrow = today"). If we don't beat persistence meaningfully, we say so and explain why (short backfill window) with the improvement path (longer history, seasonal data).
- Store all eval outputs in `evaluation/results/` as versioned JSON + a rendered `EVALUATION.md`.

### 6.4 Ward-level interpolation
- IDW (inverse distance weighting) from station points → 500m grid → aggregate to ward polygons via BigQuery GEOGRAPHY (`ST_WITHIN`). Python job on Cloud Run, runs hourly after ingest.
- **Honesty clause:** IDW from ~10–15 stations is an approximation, not measurement. Every map view carries a confidence indicator (distance-to-nearest-station). Document limitations in `docs/LIMITATIONS.md` and say it proactively in the pitch — pre-empt the sharp judge.

### 6.5 Attribution ("why is this spike coming")
- Feature-importance extraction from the boosted tree (`ML.FEATURE_IMPORTANCE`) + rule layer mapping dominant features to human causes: low wind speed + high RH → *stagnation*; hour 8–11/18–21 + high road density → *traffic*; seasonal month flags → *episodic burning*. Output: top-2 causes with confidence, per ward, per forecast. This is heuristic — label it as such in the UI ("likely drivers"), never as measured source apportionment.

## 7. ADK agents (three, mirroring VARUNA)

1. **`sentinel` (ingestion QA):** monitors feed freshness per station, flags stale (>3h) or anomalous readings (z-score jump without weather cause), maintains a station-health table the UI reads. Runs post-ingest.
2. **`oracle` (forecast & attribution):** orchestrates BQML prediction calls, assembles ward forecast + attribution payloads, answers natural-language analytical questions over BigQuery for the MP dashboard ("which 5 wards had the most exceedance days this month?"). Tool access: BigQuery read-only.
3. **`vaani` (advisory & reports):** generates (a) citizen advisories in English/Kannada/Hindi via Gemini Flash (AI Studio API) — plain language, health-action oriented, grounded ONLY in forecast JSON passed to it (no free recall — hallucination control); (b) weekly MP hotspot report via Gemini Pro (AI Studio API): top wards, trends, attributed causes, suggested interventions, rendered to PDF/HTML.

**Agent rules:** every Gemini API call (via AI Studio key, `google-genai` SDK pointed at `generativelanguage.googleapis.com`) gets structured JSON context + explicit "answer only from provided data" system instruction. Log all prompts/responses to BigQuery for audit — this also lets you track call volume against the free/low-cost tier. No agent writes to raw tables. Reserve Gemini Pro calls for final report generation runs, not iterative dev testing — use cached/mocked responses while developing agent logic to conserve budget.

## 8. API surface (FastAPI on Cloud Run)

```
GET  /wards                      → GeoJSON with current AQI surface + confidence
GET  /wards/{id}/forecast        → 24h spike prob, predicted max, attribution
GET  /stations/health            → sentinel output
GET  /reports/weekly             → latest MP report (HTML/PDF)
POST /ask                        → oracle agent NL query (dashboard chat)
GET  /advisories?lang=kn|hi|en   → current citizen advisories
```

## 9. Frontend (keep deliberately thin)

Single-page app: Leaflet map, ward choropleth (current + toggle to "tomorrow" forecast layer), click-a-ward panel (forecast, attribution, advisory), station health strip, and an "Ask VAAYU" chat box hitting `/ask`. MP report accessible as a rendered page + download. No auth, no user accounts, no mobile app. Vanilla JS or minimal React — whatever ships fastest.

## 10. Repo structure

```
vaayu/
├── CLAUDE.md                  # this file
├── docs/{BUDGET,LIMITATIONS,EVALUATION,PITCH}.md
├── ingest/                    # Cloud Run jobs: cpcb, openaq, weather, interpolate
├── ml/                        # BQML DDL/SQL, feature views, eval queries
├── agents/{sentinel,oracle,vaani}/
├── api/                       # FastAPI app
├── web/                       # frontend
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
| 0. De-risk | 0.5 | Pull 30 days CPCB Bengaluru data; audit station count, gaps, staleness. **GO/NO-GO on data quality.** |
| 1. Pipeline | 1–3 | Hourly ingest live; 90-day backfill in BigQuery; ward boundaries loaded |
| 2. Models | 4–6 | ARIMA_PLUS + boosted tree trained; temporal-split eval written to EVALUATION.md |
| 3. Spatial + API | 7–9 | IDW ward surface hourly; FastAPI endpoints live; map renders forecast layer |
| 4. Agents | 10–11 | sentinel + oracle + vaani deployed; advisories in 3 languages; /ask works |
| 5. Reports + pitch | 12–13 | Weekly MP report generator; demo script; 3-min video; BUDGET.md finalized |
| 6. Buffer | 14 | Cached demo data snapshot; submission polish |

## 13. Demo narrative (finale)

1. Open on the MP's pain: complaints about air, no ward-level evidence to act.
2. Show today's map → click a ward → **tomorrow's spike forecast + why** (attribution).
3. **Validation moment:** show yesterday's forecast vs today's actuals. Honest metrics slide (incl. per-station weakness).
4. Show the weekly MP report — "this lands in your office every Monday."
5. Cost slide: total build cost under ₹500 (near-zero ongoing), zero new hardware, existing CPCB infra, Gemini API on free/low-cost tier rather than enterprise Vertex AI infra.
6. Scale slide: config-driven city onboarding (station registry + ward GeoJSON = new city in a day). Same multi-city strategy as VARUNA.

## 14. Non-goals (do not build)

- No IoT/sensor hardware proposals. No mobile app. No user accounts/auth. No source apportionment claims beyond the labeled heuristic. No paid data. No Pub/Sub/Dataflow/GKE. No Vertex AI (endpoints, custom training, or Gemini-via-Vertex) — use the AI Studio Gemini API only. No real-time streaming — hourly is the product decision, defend it. No spend past ₹500 — re-scope before that happens, don't discover it after.

## 15. Stretch (only if Phase 5 done early)

Citizen photo-report layer (burning/dust/traffic) feeding attribution — the Track 1 hybrid. Sentinel-5P NO2 overlay. Kannada voice advisory via TTS.


## Git Commit Guidelines
- Do not include AI attribution or co-author lines in commit messages.