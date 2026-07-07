# BUDGET — VAAYU (₹500 hard cap)

This file is load-bearing. Every BQML training/prediction query logs its
`--dry_run` bytes here **before** it runs for real. Every paid-tier risk gets a
written estimate here before the service is used.

## Running total

| Date | Item | Est. cost (₹) | Running total (₹) | Notes |
|---|---|---|---|---|
| 2026-07-07 | Phase 0 data audit (data.gov.in + OpenAQ + Open-Meteo) | 0 | 0 | All free public APIs, no GCP billing |

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
| — | — | — | — |
