"""VAAYU FastAPI backend (CLAUDE.md §8) — serves the ward/grid surfaces,
per-station forecasts, and station health from BigQuery.

Tier A (grid) is the nationwide default; ward mode is additive where a
validated GeoJSON exists (none yet, so every city returns grid — the honest
default, surfaced in the response `tier`/`mode` fields).

Results are cached in-memory with a short TTL: the surfaces refresh hourly, so
querying BigQuery on every request would waste latency and free-tier bytes.

Run locally: uvicorn api.main:app --reload --port 8080
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Reuse the shared BigQuery helper + agent code (single image contains all dirs).
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "ingest"))
sys.path.insert(0, str(_ROOT / "agents"))
sys.path.insert(0, str(_ROOT / "agents" / "oracle"))
import bq  # noqa: E402
from google.cloud import bigquery  # noqa: E402
from pydantic import BaseModel  # noqa: E402

app = FastAPI(title="VAAYU API", version="0.3.0",
              description="Ward-level air-quality decision intelligence")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

CACHE_TTL = 300  # seconds
_cache: dict[str, tuple[float, Any]] = {}


def _query(sql: str, params: list | None = None, cache_key: str | None = None) -> list[dict]:
    if cache_key and cache_key in _cache:
        ts, val = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return val
    cfg = bigquery.QueryJobConfig(query_parameters=params or [])
    rows = [dict(r) for r in bq.client().query(sql, job_config=cfg, location=bq.BQ_LOCATION).result()]
    if cache_key:
        _cache[cache_key] = (time.time(), rows)
    return rows


def _sp(name: str, value: str) -> bigquery.ScalarQueryParameter:
    return bigquery.ScalarQueryParameter(name, "STRING", value)


def _require_city(city: str) -> None:
    known = {c["city_id"] for c in _query(
        f"SELECT city_id FROM `{bq.table_fqn('cities')}`", cache_key="city_ids")}
    if city not in known:
        raise HTTPException(404, f"Unknown city '{city}'. Known: {sorted(known)}")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/cities")
def cities() -> dict:
    sql = f"""
    SELECT c.city_id, c.name, c.state, c.tier,
      c.lon_min, c.lat_min, c.lon_max, c.lat_max,
      (SELECT COUNT(*) FROM `{bq.table_fqn('station_forecast')}` sf WHERE sf.city_id=c.city_id) AS n_stations,
      (SELECT MAX(generated_at) FROM `{bq.table_fqn('city_grid_surface')}` g WHERE g.city_id=c.city_id) AS surface_generated_at
    FROM `{bq.table_fqn('cities')}` c
    ORDER BY c.priority
    """
    rows = _query(sql, cache_key="cities")
    for r in rows:
        r["center"] = [(r["lon_min"] + r["lon_max"]) / 2, (r["lat_min"] + r["lat_max"]) / 2]
        r["mode"] = "ward" if r["tier"] == "B" else "grid"
    return {"cities": rows}


@app.get("/surface")
def surface(city: str = Query(...), layer: str = Query("forecast", pattern="^(forecast|current)$")) -> JSONResponse:
    """GeoJSON grid surface. layer=forecast -> tomorrow's predicted max PM2.5;
    layer=current -> latest interpolated PM2.5. Every cell carries confidence."""
    _require_city(city)
    value_col = "pred_max_pm25_24h" if layer == "forecast" else "current_pm25"
    sql = f"""
    SELECT cell_lat, cell_lon, {value_col} AS value, breach_prob,
           pred_category, confidence, ROUND(dist_nearest_km,1) AS dist_nearest_km
    FROM `{bq.table_fqn('city_grid_surface')}`
    WHERE city_id=@city
    """
    rows = _query(sql, [_sp("city", city)], cache_key=f"surface:{city}:{layer}")
    features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [r["cell_lon"], r["cell_lat"]]},
        "properties": {
            "value": round(r["value"], 1) if r["value"] is not None else None,
            "breach_prob": round(r["breach_prob"], 3) if r["breach_prob"] is not None else None,
            "category": r["pred_category"], "confidence": r["confidence"],
            "dist_nearest_km": r["dist_nearest_km"],
        },
    } for r in rows]
    return JSONResponse({
        "type": "FeatureCollection", "city": city, "layer": layer,
        "mode": "grid", "cell_size_deg": 0.01, "features": features,
    })


@app.get("/stations")
def stations(city: str = Query(...)) -> JSONResponse:
    """Per-station forecast points (current, tomorrow's max, breach prob)."""
    _require_city(city)
    sql = f"""
    SELECT station_id, station, latitude, longitude, as_of,
           ROUND(current_pm25,1) current_pm25, ROUND(pred_max_pm25_24h,1) pred_max_pm25_24h,
           ROUND(breach_prob,3) breach_prob, pred_category, pred_breach_naaqs
    FROM `{bq.table_fqn('station_forecast')}` WHERE city_id=@city
    """
    rows = _query(sql, [_sp("city", city)], cache_key=f"stations:{city}")
    features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
        "properties": {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                       for k, v in r.items() if k not in ("latitude", "longitude")},
    } for r in rows]
    return JSONResponse({"type": "FeatureCollection", "city": city, "features": features})


@app.get("/stations/health")
def stations_health(city: str = Query(...)) -> dict:
    """sentinel agent output: per-station freshness + anomaly flags."""
    _require_city(city)
    sql = f"""
    SELECT station_id, station, latest_ts, age_hours, stale, latest_pm25,
           zscore, anomaly, note
    FROM `{bq.table_fqn('station_health')}` WHERE city_id=@city
    ORDER BY age_hours DESC
    """
    rows = _query(sql, [_sp("city", city)], cache_key=f"health:{city}")
    out = [{
        "station_id": r["station_id"], "station": r["station"],
        "latest": r["latest_ts"].isoformat() if r["latest_ts"] else None,
        "age_hours": r["age_hours"], "stale": r["stale"],
        "latest_pm25": r["latest_pm25"], "zscore": r["zscore"],
        "anomaly": r["anomaly"], "note": r["note"],
    } for r in rows]
    return {"city": city, "n_stations": len(out),
            "n_stale": sum(1 for s in out if s["stale"]),
            "n_anomaly": sum(1 for s in out if s["anomaly"]), "stations": out}


@app.get("/advisories")
def advisories(city: str = Query(...), lang: str | None = Query(None)) -> dict:
    """vaani citizen advisories for a city (all languages, or one via ?lang=)."""
    _require_city(city)
    where = "city_id=@city" + (" AND lang=@lang" if lang else "")
    params = [_sp("city", city)] + ([_sp("lang", lang)] if lang else [])
    sql = f"""
    SELECT lang, category, headline, body, health_actions, as_of, generated_at
    FROM `{bq.table_fqn('advisories')}` WHERE {where} ORDER BY lang
    """
    rows = _query(sql, params, cache_key=f"adv:{city}:{lang}")
    for r in rows:
        for k in ("as_of", "generated_at"):
            if r.get(k) is not None:
                r[k] = r[k].isoformat()
    return {"city": city, "advisories": rows}


class AskBody(BaseModel):
    question: str


@app.post("/ask")
def ask_endpoint(body: AskBody) -> dict:
    """oracle agent: grounded NL Q&A over the current forecast snapshot."""
    if not body.question.strip():
        raise HTTPException(400, "question is required")
    from ask import ask  # oracle.ask (lazy: only /ask needs Gemini)
    return ask(body.question)


@app.get("/reports/weekly")
def weekly_report(city: str = Query(...)) -> JSONResponse:
    """Latest weekly MP report (HTML) for a city, if generated."""
    _require_city(city)
    rows = _query(
        f"SELECT html, generated_at FROM `{bq.table_fqn('reports')}` "
        f"WHERE city_id=@city ORDER BY generated_at DESC LIMIT 1",
        [_sp("city", city)], cache_key=f"report:{city}")
    if not rows:
        raise HTTPException(404, f"No weekly report generated yet for {city}.")
    from fastapi.responses import HTMLResponse
    return HTMLResponse(rows[0]["html"])


@app.get("/forecast")
def forecast(city: str = Query(...)) -> dict:
    """City-level summary: worst forecast cells + breach outlook."""
    _require_city(city)
    summ = _query(f"""
    SELECT COUNT(*) cells, COUNTIF(pred_max_pm25_24h>=60) breach_cells,
      ROUND(MAX(pred_max_pm25_24h),1) max_pred, ROUND(AVG(breach_prob),3) avg_breach_prob,
      MAX(generated_at) generated_at
    FROM `{bq.table_fqn('city_grid_surface')}` WHERE city_id=@city
    """, [_sp("city", city)], cache_key=f"fc_summ:{city}")[0]
    worst = _query(f"""
    SELECT station, ROUND(pred_max_pm25_24h,1) pred, ROUND(breach_prob,3) breach_prob, pred_category
    FROM `{bq.table_fqn('station_forecast')}` WHERE city_id=@city
    ORDER BY pred_max_pm25_24h DESC LIMIT 5
    """, [_sp("city", city)], cache_key=f"fc_worst:{city}")
    return {
        "city": city,
        "generated_at": summ["generated_at"].isoformat() if summ["generated_at"] else None,
        "grid_cells": summ["cells"], "breach_cells": summ["breach_cells"],
        "max_predicted_pm25": summ["max_pred"], "avg_breach_prob": summ["avg_breach_prob"],
        "worst_stations": worst,
    }


# Serve the single-page frontend from the same container (one origin, one deploy).
# Mounted last so it never shadows the API routes above.
_WEB = Path(__file__).resolve().parent.parent / "web"
if _WEB.exists():
    app.mount("/", StaticFiles(directory=str(_WEB), html=True), name="web")
