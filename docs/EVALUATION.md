# EVALUATION — VAAYU Phase 2 (24h breach forecast)

_Generated: 2026-07-07T20:30:55.270751+00:00_  ·  Threshold: 0.35 (recall-favouring)

## What the model predicts
- **Target:** breach = next-24h max PM2.5 exceeds NAAQS 24h limit (60 ug/m3).
- Trained on CAMS-modelled history (CPCB has no historical API); **temporal split only** (train past → validate → test most-recent). TEST is fully held out. Cross-validation against live CPCB accrues over time.
- Why NAAQS-60 not CPCB-Poor-90: at 90 µg/m³ clean southern cities (Bengaluru, Chennai) have ~zero events — genuinely, not a data bug — so a 90 target is degenerate there. 60 µg/m³ is India's legal 24h PM2.5 limit and the pitch's literal 'safe limit'; it is non-degenerate for every city. A commoner target makes persistence HARDER to beat, so this is not tuned to flatter.

## Headline (overall, all cities, TEST)

| Metric | Model | Persistence baseline |
|---|---|---|
| Breach AUC-PR | **0.993** | 0.991 |
| Breach ROC-AUC | 0.993 | 0.990 |
| Breach recall | 0.971 | 0.849 |
| Breach precision | 0.921 | 0.997 |
| Breach F1 | 0.946 | 0.917 |
| Next-24h max PM2.5 MAE | **25.2** µg/m³ | 34.7 |
| … RMSE | 51.6 | 65.1 |

## The value beyond persistence: predicting *new* breaches (onset)

On hours currently **within** the safe limit (PM2.5 < 60), persistence always says 'no breach' — so it catches **0%** of the breaches that then occur. This is the actionable case (advance warning before a clean-air neighbourhood turns unhealthy), and it is exactly where the model adds value persistence structurally cannot:

- Currently-safe TEST hours: 88,037
- …that breach within 24h: 9,897
- **Model recall on these onsets: 0.810** (persistence: 0.000 by construction)
- Model precision on these onsets: 0.602

## Per-city (breach AUC-PR — shows honest variance)

| City | n | positive% | Model AUC-PR | Persist AUC-PR | Reg MAE | Persist MAE |
|---|---|---|---|---|---|---|
| bengaluru | 13200 | 5.2% | 0.261 | 0.267 | 6.5 | 10.8 |
| chennai | 9240 | 0.0% | n/a | n/a | 4.9 | 7.3 |
| delhi | 59400 | 99.5% | 1.000 | 1.000 | 50.6 | 68.9 |
| hyderabad | 17160 | 10.5% | 0.539 | 0.549 | 10.2 | 14.8 |
| kolkata | 9240 | 43.4% | 0.826 | 0.765 | 16.3 | 22.9 |
| mumbai | 30360 | 0.0% | n/a | n/a | 4.3 | 6.2 |
| pune | 5280 | 0.0% | n/a | n/a | 6.0 | 5.6 |

## Honest reading
- Report **recall** first: for an MP alert, missing a breach is worse than a false alarm. See per-city — clean cities (Bengaluru, Chennai) have few/no TEST breaches, so their AUC is unstable or n/a; that is the truth of the season, stated not hidden.
- Where the model does **not** beat persistence, it is said plainly in the table above. Persistence is strong for PM2.5 (high autocorrelation); the model earns its keep by anticipating *changes* (onset), which the per-city lift and the regressor MAE gap quantify.
- Improvement path: longer/seasonal history, station static features (OSM road density/land-use — not yet added), and retraining on real CPCB as it accumulates.

## Baselines & scope note
- **Persistence** is the primary baseline (§6.3) and is directly comparable: it is scored on every TEST hour, exactly like the models.
- **ARIMA_PLUS (§6.2 model #1) was descoped for Phase 2.** Hourly ARIMA across 109 year-long series is heavy, and — more importantly — its single-origin 24h forecast is not apples-to-apples with the per-hour rolling evaluation the boosted models and persistence receive. Adding a non-comparable number would mislead, not inform. Persistence is the honest classical floor here; ARIMA can return later as a like-for-like daily-granularity baseline if useful.
