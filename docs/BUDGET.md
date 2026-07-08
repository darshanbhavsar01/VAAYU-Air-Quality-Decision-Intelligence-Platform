# BUDGET — VAAYU (₹500 hard cap)

This file is load-bearing. Every BQML training/prediction query logs its
`--dry_run` bytes here **before** it runs for real. Every paid-tier risk gets a
written estimate here before the service is used.

## Running total

| Date | Item | Est. cost (₹) | Running total (₹) | Notes |
|---|---|---|---|---|
| 2026-07-07 | Phase 0 data audit (data.gov.in + WAQI + Open-Meteo) | 0 | 0 | All free public APIs, no GCP billing |
| 2026-07-08 | Phase 1 BigQuery: dataset+schema, CPCB ingest (735 rows), 91-day weather backfill (13k rows) | 0 | 0 | Load jobs are free; MERGE queries scan KBs, far inside 1TB/mo free tier. Storage ~few MB (<10GB free). |
| 2026-07-08 | Phase 2 CAMS full-year backfill (947k rows) + 2 BQML trainings (~36GB billed) | 0 | 0 | ~1.5GB storage (<10GB free); training 3.6% of 1TB/mo query free tier |
| 2026-07-08 | Phase 3 deploy: Cloud Build image, Cloud Run service (min-inst=0), 1 hourly Job, 1 Scheduler | 0 | 0 | Build 120min/day free; service no idle cost; job ~2min/hr within 360k GB-s free; scheduler first 3 free |

**Hourly pipeline query cost:** each run rebuilds the feature table (~91 MB scan) + tiny ML.PREDICT + interpolate ≈ ~0.1 GB/run → ~70 GB/month, ~7% of the 1TB free tier. Optimisation path if needed: refresh only recent partitions instead of the full-year feature rebuild.

### Gemini (AI Studio, free tier — NOT Vertex, off the GCP bill)
| Item | Model | Volume | Cost |
|---|---|---|---|
| vaani advisories | flash cascade (see below) | ~20 calls/generation (7 cities × EN+HI+regional) | ₹0 (free tier) |
| oracle /ask | flash cascade | on demand | ₹0 |
| vaani weekly report | pro cascade → flash cascade | ~1/city, run rarely | ₹0 |

**Quota realities (learned the hard way, logged so we don't re-trip them):**
- Every Gemini model has its own small **per-account, per-day** free quota (`gemini-2.5-flash` is just 20 requests/day). One advisory generation run (~20 calls) can exhaust a single model on a single account.
- **Fix: a model+account fallback chain** (`agents/common.py`), entirely free:
  1. **Model cascade** (same AI Studio account): `gemini-2.5-flash` → `2.5-flash-lite` → `2.0-flash` → `2.0-flash-lite` → `3-flash-preview` → `3.1-flash-lite` → `3.5-flash` → `flash-latest`. Each is a separate quota pool, so cycling through them multiplies the effective daily capacity on one account for free.
  2. **Account cascade**: once every model above is exhausted on the current AI Studio account, move to the next configured account (`GEMINI_API_KEY_FALLBACK1`, `FALLBACK2` — 2 additional free accounts, each with its own full quota pool). 3 accounts × 8 models ≈ 24 independent free quota pools.
  3. Pro tasks (weekly report) cascade Pro variants first, then fall through to the same flash cascade rather than failing outright.
  - Known-exhausted (account, model) pairs are skipped for the rest of the process (no wasted retries); `agent_logs.key_name` records exactly which account/model served every call, for audit.
  - **Verified**: advisory coverage was stuck at 5/20 for a full day (primary account's flash models all 429/503); the fallback chain completed all 20 in one run by cascading to `gemini-3-flash-preview` on the primary account — no fallback account even needed that time. Failover to `fallback1` was also unit-tested directly (simulated full primary exhaustion → correctly routed to fallback1).
- Advisory/report generation runs on a **daily** cadence, NOT in the hourly pipeline (hourly × 20 calls would blow any free daily quota even with the cascade).
- Advisories use **upsert** (never truncate), so partial runs under a flaky/rate-limited tier accumulate coverage instead of wiping good rows.

**Current total: ₹0 / ₹500.**

## Budget alerts (action item — do on day 1 before GCP work)

- [ ] GCP budget alert at ₹100
- [ ] GCP budget alert at ₹250
- [ ] GCP budget alert at ₹400

## Service plan (from CLAUDE.md §3.1)

| Service | Expected cost | Guardrail |
|---|---|---|
| BigQuery storage | ₹0 | <10GB free tier |
| BigQuery queries | ₹0 | <1TB/mo; no `SELECT *` on wide tables |
| BQML training | Watch | `--dry_run` every train; narrow feature views; train once per phase |
| Cloud Run | ₹0–~50 | min-instances=0 |
| Cloud Scheduler | ₹0 | first 3 jobs free |
| Gemini API (AI Studio) | ~₹100–200 | Flash for advisories, Pro only for final reports; cache dev responses |
| Firebase Hosting | ₹0 | free tier |
| Secret Manager | ₹0 | ≤6 active versions |

## BQML dry-run log

_(append one row per training/prediction query: date · query file · bytes billed · ₹ est.)_

| Date | Query | Bytes | Est. ₹ |
|---|---|---|---|
| 2026-07-08 | features.sql (feature table build) | 91 MB | 0 (free tier) |
| 2026-07-08 | spike_classifier.sql (BOOSTED_TREE train) dry-run | 274 MB | 0 (free tier) |
| 2026-07-08 | pm25_regressor.sql (BOOSTED_TREE train) dry-run | 274 MB | 0 (free tier) |
| 2026-07-08 | spike_classifier train (ACTUAL billed — boosting scans data ×iters) | 21.4 GB | 0 (2.1% of 1TB/mo free) |
| 2026-07-08 | pm25_regressor train (ACTUAL billed) | 15.0 GB | 0 (1.5% of 1TB/mo free) |

**BQML note:** boosted-tree training bills far more than the single-scan dry-run (iterations re-scan). ~36 GB for both models this phase — still comfortably free. Retrain sparingly (once per phase) to preserve the 1TB/month headroom.
