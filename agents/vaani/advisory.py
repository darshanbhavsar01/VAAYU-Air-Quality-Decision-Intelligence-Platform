"""vaani — citizen advisory generator (CLAUDE.md §7.3a).

For each city, builds a compact forecast context from BigQuery and asks Gemini
Flash for a plain-language health advisory in every required language:
  English + Hindi ALWAYS, plus the city's regional language
  (Kannada/Marathi/Tamil/Bengali/Telugu).
Advisories are grounded ONLY in the forecast JSON (no free recall) and written
to the `advisories` table (WRITE_TRUNCATE — regenerated as a set).

Run: python agents/vaani/advisory.py
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Native scripts (Kannada/Tamil/…) must survive console printing on Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "ingest"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bq  # noqa: E402
from cities import load_cities  # noqa: E402
from common import FLASH_MODEL, generate  # noqa: E402

LANG_NAMES = {
    "en": "English", "hi": "Hindi (हिन्दी, Devanagari script)",
    "kn": "Kannada (ಕನ್ನಡ script)", "mr": "Marathi (मराठी, Devanagari script)",
    "ta": "Tamil (தமிழ் script)", "bn": "Bengali (বাংলা script)",
    "te": "Telugu (తెలుగు script)",
}

ADV_COLUMNS = ["city_id", "lang", "as_of", "category", "headline", "body",
               "health_actions", "model", "generated_at"]


def advisory_langs(city) -> list[str]:
    """English + Hindi always, then the city's regional language(s)."""
    langs = ["en", "hi"]
    for l in city.languages:
        if l not in langs:
            langs.append(l)
    return langs


def forecast_context(city_id: str, city_name: str) -> dict | None:
    sql = f"""
    WITH sf AS (SELECT * FROM `{bq.table_fqn('station_forecast')}` WHERE city_id=@c)
    SELECT
      (SELECT AS STRUCT
         ROUND(MAX(pred_max_pm25_24h),1) max_pred,
         ROUND(AVG(breach_prob),3) avg_breach_prob,
         COUNTIF(pred_breach_naaqs) breach_stations,
         COUNT(*) n_stations,
         MAX(as_of) as_of
       FROM sf) AS summary,
      ARRAY(SELECT AS STRUCT station, ROUND(pred_max_pm25_24h,1) pred, pred_category
            FROM sf ORDER BY pred_max_pm25_24h DESC LIMIT 3) AS worst
    """
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", city_id)])
    rows = list(bq.client().query(sql, job_config=cfg, location=bq.BQ_LOCATION).result())
    if not rows or rows[0]["summary"]["n_stations"] == 0:
        return None
    s = rows[0]["summary"]
    max_pred = s["max_pred"]
    cat = ("Good" if max_pred <= 30 else "Satisfactory" if max_pred <= 60 else
           "Moderate" if max_pred <= 90 else "Poor" if max_pred <= 120 else
           "Very Poor" if max_pred <= 250 else "Severe")
    return {
        "city": city_name,
        "as_of": s["as_of"].isoformat() if s["as_of"] else None,
        "predicted_max_pm25_next_24h": max_pred,
        "predicted_category": cat,
        "exceeds_safe_limit_60": bool(max_pred >= 60),
        "breach_probability": s["avg_breach_prob"],
        "stations_expected_to_breach": f"{s['breach_stations']} of {s['n_stations']}",
        "worst_areas": [{"area": w["station"], "pm25": w["pred"], "category": w["pred_category"]}
                        for w in rows[0]["worst"]],
    }


def make_advisory(city_id: str, city_name: str, ctx: dict, lang: str) -> dict:
    import json
    prompt = (
        f"Tomorrow's PM2.5 air-quality forecast for {city_name}, India (data below).\n"
        f"India's 24-hour safe limit is 60 µg/m³.\n\n"
        f"FORECAST DATA (the only facts you may use):\n{json.dumps(ctx, ensure_ascii=False, indent=2)}\n\n"
        f"Write a citizen air-quality advisory for tomorrow, in {LANG_NAMES[lang]}. "
        f"Ground every statement in the data above — do not invent numbers or places. "
        f"Match the tone to the category: reassure when air is Good/Satisfactory; warn "
        f"clearly and name protective actions when Moderate or worse, especially for "
        f"sensitive groups (children, elderly, respiratory/heart patients, outdoor workers). "
        f"Return JSON with exactly these keys, ALL written in {LANG_NAMES[lang]}:\n"
        f'  "headline": one short line (max ~12 words)\n'
        f'  "body": 2-3 plain sentences on what tomorrow\'s air will be like\n'
        f'  "health_actions": 1-2 concrete actions people should take\n'
    )
    for attempt in range(2):  # retry once if the model returns empty fields
        out = generate("vaani", "advisory", prompt, city_id=city_id, lang=lang, as_json=True)
        out = out if isinstance(out, dict) else json.loads(out)
        if out.get("headline") and out.get("body"):
            return out
    return out


def _existing() -> set[tuple[str, str]]:
    """(city_id, lang) advisories already present with non-empty content."""
    sql = f"SELECT city_id, lang FROM `{bq.table_fqn('advisories')}` WHERE headline != '' AND body != ''"
    try:
        return {(r.city_id, r.lang) for r in bq.client().query(sql, location=bq.BQ_LOCATION).result()}
    except Exception:  # noqa: BLE001
        return set()


def run(skip_existing: bool = True) -> int:
    now = pd.Timestamp(datetime.now(timezone.utc))
    done = _existing() if skip_existing else set()
    rows = []
    for city in load_cities():
        ctx = None
        for lang in advisory_langs(city):
            if (city.city_id, lang) in done:
                continue
            if ctx is None:  # fetch forecast lazily, only when a lang is needed
                ctx = forecast_context(city.city_id, city.name)
                if ctx is None:
                    print(f"  {city.name}: no forecast yet, skipping")
                    break
            try:
                time.sleep(1.0)  # stay under free-tier requests-per-minute
                adv = make_advisory(city.city_id, city.name, ctx, lang)
                rows.append({
                    "city_id": city.city_id, "lang": lang, "as_of": ctx["as_of"],
                    "category": ctx["predicted_category"],
                    "headline": adv.get("headline", ""), "body": adv.get("body", ""),
                    "health_actions": adv.get("health_actions", ""),
                    "model": FLASH_MODEL, "generated_at": now,
                })
                print(f"  {city.name} [{lang}]: {adv.get('headline','')[:50]}")
            except Exception as e:  # noqa: BLE001
                print(f"  {city.name} [{lang}]: FAILED {type(e).__name__}: {e}")
    if not rows:
        print("No advisories generated (all calls failed).")
        return 0
    df = pd.DataFrame(rows, columns=ADV_COLUMNS)
    df["as_of"] = pd.to_datetime(df["as_of"], utc=True)
    # Upsert, never truncate — a partial run accumulates rather than wiping
    # advisories that succeeded earlier (Gemini free tier can be flaky).
    bq.load_and_merge(df, "_staging_advisories", "merge_advisories.sql")
    print(f"Upserted {len(df)} advisories across {df['city_id'].nunique()} cities.")
    return len(df)


if __name__ == "__main__":
    run()
