# VAAYU — Nationwide Air-Quality Decision Intelligence

**Not another AQI dashboard.** VAAYU tells any MP's office, in any Indian city, **which neighbourhoods will breach safe air limits tomorrow, why, and what to do about it** — using only existing public infrastructure and near-zero cloud cost.

> **Track 2 (Pollution Hotspot Detection)** · Build with AI: Code for Communities (Hack2skill × GDG)
> Problem statement submitted by a sitting Member of Parliament. Winning solutions get piloted in real constituencies.

## Live demo

**https://vaayu-api-229692962627.asia-south1.run.app/** — pick a city, see tomorrow's forecast map, click a neighbourhood, and get the spike forecast, likely drivers, a citizen advisory in the local language, and a weekly MP report.

---

## The problem

An MP gets complaints about air quality but has **no ward-level, forward-looking evidence** to act on. Existing dashboards show *yesterday's* city-average AQI. They don't say *which* neighbourhood will be unhealthy *tomorrow*, or *why*, or *what to do*.

## What VAAYU does

| Capability | Detail |
|---|---|
| **Neighbourhood hotspot maps** | ~1 km grid interpolated from CPCB stations, for **every** Indian city with a monitor |
| **24-hour spike forecast** | ML predicts tomorrow's max PM2.5 plus the probability of breaching the 60 µg/m³ safe limit, per station |
| **Likely drivers** | Heuristic attribution (stagnation / traffic / accumulation) — labelled as "likely", never as measured source apportionment |
| **Citizen advisories** | Plain-language health guidance in **English + Hindi + the city's regional language** (Kannada, Marathi, Tamil, Bengali, Telugu) |
| **Weekly MP report** | Auto-generated per constituency: outlook, top hotspots, recommended interventions |
| **Ask VAAYU** | Natural-language Q&A over the live forecast ("which city is worst tomorrow?", "compare Delhi and Mumbai") |
| **Feed health** | Per-station freshness and anomaly monitoring |

**7 cities live today** — Bengaluru, Delhi, Mumbai, Chennai, Kolkata, Hyderabad, Pune. Adding a city is **one line of YAML** — no code, no redeploy.

---

## Architecture

```
config/cities.yaml  --->  the entire multi-city mechanism is "add a row here"
       |
       v
Cloud Scheduler (hourly) ---> Cloud Run Job: pipeline
       |   - ingest CPCB (data.gov.in) ---> BigQuery raw_aqi + stations
       |   - ingest weather (Open-Meteo) ---> raw_weather
       |   - ingest CAMS air quality ---> aqi_cams   (training-history backbone)
       |   - build features (lags, rolling, weather, temporal)
       |   - BQML predict ---> station_forecast     (2 global boosted-tree models)
       |   - IDW interpolate ---> city_grid_surface (+ distance-to-station confidence)
       |   - sentinel QA ---> station_health
       |
Cloud Scheduler (daily) ---> Cloud Run Job: vaani
       |   - advisories (EN + HI + regional) ---> advisories
       |   - weekly MP reports ---> reports
       |
       v
Cloud Run Service: FastAPI + landing page + Leaflet map  <--- reads BigQuery surfaces
```

**Stack:** Cloud Run (service + jobs) · Cloud Scheduler · BigQuery + BQML · Gemini API (AI Studio, *not* Vertex) · FastAPI · Leaflet · Secret Manager. Everything runs on **GCP free tier** in `asia-south1` (data stays in India).

---

## The ML, honestly

**Target:** `breach` = next-24h max PM2.5 exceeds India's NAAQS 24-hour limit (60 µg/m³).
**Models:** one *global* `BOOSTED_TREE_CLASSIFIER` (breach probability) and one `BOOSTED_TREE_REGRESSOR` (next-24h max PM2.5), trained across all cities with `city_id`/`station_id` as features. **Temporal split only** (train past, validate, test most-recent); the test set is fully held out.

### Results (TEST set, all cities)

| Metric | **VAAYU model** | Persistence baseline |
|---|---|---|
| Breach AUC-PR | **0.993** | 0.991 |
| Breach recall | **0.971** | 0.849 |
| Next-24h max PM2.5 MAE | **25.2 µg/m³** | 34.7 |

**Where it actually earns its keep — predicting *new* breaches:** on hours currently *within* the safe limit, persistence catches **0%** of the breaches that then occur (it always says "same as now"). VAAYU catches **81%** — that is the advance warning an MP can act on.

We report the weak numbers too: our training window is monsoon-heavy, when southern cities (Bengaluru, Chennai) genuinely have near-zero breaches — so their per-city scores are unstable or n/a. We show that openly rather than hiding it. Where the model does not beat persistence, we say so.

> **Data-source honesty:** CPCB has no historical API, so the models train on **CAMS reanalysis** (ECMWF, via Open-Meteo) — clearly labelled, kept in a separate table, and cross-validated against live CPCB as it accrues.

---

## Engineering highlights

- **Config-driven nationwide onboarding** — `python scripts/onboard_city.py <city>` validates CPCB coverage, backfills a year of weather and CAMS history, and the city appears in every surface. No code change.
- **Grid mode is the honest default.** Every map cell carries a *distance-to-nearest-station* confidence tier — IDW from sparse stations is an approximation, and we say so on the map. Ward mode is additive, only where a validated boundary file exists.
- **Idempotent everything** — staging plus `MERGE` on every ingest; re-running never duplicates a row. The hourly job is fault-tolerant, so a flaky government feed never brings the pipeline down.
- **Grounded agents** — every language-model call is given a strict "answer only from the provided data" instruction plus the forecast JSON; no free recall, hallucination-controlled.

---

## Cost

**Total build cost: ₹0**, against a ₹500 hard cap. Every service sits inside the GCP free tier (Cloud Run min-instances=0, BigQuery under 10 GB storage / 1 TB queries, Gemini on the AI Studio free tier — *not* enterprise Vertex AI). Zero new hardware, existing CPCB infrastructure, near-zero ongoing cost.

---

## Repository layout

```
config/cities.yaml          # city registry -- one row per city
ingest/                     # CPCB, weather, CAMS ingest + BigQuery helpers + city onboarding
ml/                         # BQML models, feature engineering, IDW interpolation (versioned SQL)
agents/{sentinel,oracle,vaani}/   # the three agents (QA, NL Q&A, advisories + reports)
api/main.py                 # FastAPI backend (also serves the site)
web/index.html              # landing page
web/app.html                # Leaflet map application
infra/bigquery/*.sql        # table schemas + MERGE statements
infra/deploy.sh             # full Cloud Run + Scheduler deploy
pipeline.py                 # hourly Cloud Run Job entrypoint
Dockerfile                  # one image serves both the API and the jobs
```

## Running it yourself

```bash
# 1. Config
cp .env.example .env        # fill in DATA_GOV_IN_API_KEY, GEMINI_API_KEY, GCP_PROJECT_ID, ...
pip install -r requirements.txt

# 2. BigQuery schema + a first city
python infra/bigquery/setup_schema.py
python scripts/onboard_city.py bengaluru

# 3. Build the surfaces + run the API
python pipeline.py
uvicorn api.main:app --port 8080      # open http://localhost:8080

# 4. Deploy to Cloud Run (service + hourly + daily jobs + schedulers)
bash infra/deploy.sh
```

## API

| Endpoint | Purpose |
|---|---|
| `GET /cities` | onboarded cities + tier + coverage |
| `GET /surface?city=&layer=forecast\|current` | grid GeoJSON + per-cell confidence |
| `GET /stations?city=` and `GET /stations/health?city=` | per-station forecast and feed health |
| `GET /forecast?city=` | city outlook + worst hotspots |
| `GET /advisories?city=&lang=` | citizen advisories |
| `POST /ask` `{"question": ...}` | grounded NL Q&A |
| `GET /reports/weekly?city=` | rendered weekly MP report (HTML) |

Base URL: **https://vaayu-api-229692962627.asia-south1.run.app/**

---

## Known limitations (stated up front)

- **Ward mode not yet enabled** for any city — all 7 ship in grid mode (the honest nationwide default). Ward-level detail needs a validated municipal boundary file per city; sourcing Bengaluru's is the next upgrade.
- **CPCB live ingest is blocked from datacenter IPs** — data.gov.in drops Cloud Run connections, so the hourly job's CPCB step is fault-tolerant (non-fatal); the forecast product (CAMS-driven) stays live regardless.
- **Attribution is heuristic**, not measured source apportionment — labelled as such everywhere.

---

Built for real constituency deployment: existing CPCB infrastructure, zero new hardware, near-zero ongoing cost, and a paper trail that survives a sharp technical judge.

Built by [Darshan Bhavsar](https://www.linkedin.com/in/darshan01/).
