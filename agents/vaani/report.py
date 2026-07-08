"""vaani weekly MP hotspot report (CLAUDE.md §7.3b).

Builds a grounded, per-city report for an MP's office: outlook, top hotspots
with likely (heuristic) drivers, and suggested interventions. Gemini Pro writes
the prose as structured JSON; we render it into a fixed HTML template with an
always-present methodology/caveats footer (honesty — CAMS-modelled, heuristic
attribution). Falls back to Flash if Pro quota is exhausted.

Run: python agents/vaani/report.py [city_id ...]   (default: delhi bengaluru)
"""
from __future__ import annotations

import html as _html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "ingest"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bq  # noqa: E402
from cities import get_city  # noqa: E402
from common import FLASH_MODEL, PRO_MODEL, generate  # noqa: E402


def _heuristic_driver(wind: float | None, rh: float | None, cat: str) -> str:
    if wind is not None and wind < 2.0:
        return "stagnation (low wind)"
    if rh is not None and rh > 80:
        return "moisture trapping / stagnation"
    if cat in ("Poor", "Very Poor", "Severe"):
        return "sustained accumulation"
    return "dispersion favourable"


def build_context(city_id: str, city_name: str) -> dict | None:
    sql = f"""
    SELECT station, ROUND(pred_max_pm25_24h,1) pred, pred_category,
           ROUND(current_pm25,1) current_pm25, ROUND(breach_prob,3) breach_prob,
           ROUND(fwd24_wind_mean,2) wind, ROUND(fwd24_rh_mean,1) rh, as_of
    FROM `{bq.table_fqn('station_forecast')}` WHERE city_id=@c
    ORDER BY pred_max_pm25_24h DESC
    """
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", city_id)])
    rows = [dict(r) for r in bq.client().query(sql, job_config=cfg, location=bq.BQ_LOCATION).result()]
    if not rows:
        return None
    for r in rows:
        r["likely_driver"] = _heuristic_driver(r["wind"], r["rh"], r["pred_category"])
        r["as_of"] = r["as_of"].isoformat() if r["as_of"] else None
    n_breach = sum(1 for r in rows if r["pred"] >= 60)
    return {
        "city": city_name, "as_of": rows[0]["as_of"],
        "n_stations": len(rows), "stations_breaching_naaqs60": n_breach,
        "hotspots": rows[:8],
    }


def generate_report(city_id: str) -> str:
    city = get_city(city_id)
    ctx = build_context(city_id, city.name)
    if ctx is None:
        raise SystemExit(f"No forecast data for {city_id}")
    prompt = (
        f"You are writing the weekly air-quality briefing for the Member of Parliament's "
        f"office covering {city.name}, India. India's NAAQS 24-hour PM2.5 safe limit is 60 µg/m³.\n\n"
        f"GROUNDING DATA (next-24h forecast per monitoring area; the ONLY facts you may use):\n"
        f"{json.dumps(ctx, ensure_ascii=False, indent=2)}\n\n"
        f"'likely_driver' is a HEURISTIC label from weather (low wind/high humidity), not "
        f"measured source apportionment — present it as a 'likely driver', never as certainty.\n\n"
        f"Return JSON with keys:\n"
        f'  "title": string\n'
        f'  "exec_summary": 2-3 sentence overview for a busy MP\n'
        f'  "outlook": one paragraph on tomorrow\'s expected air quality\n'
        f'  "hotspots": array of up to 5 {{"area","forecast_pm25","category","likely_driver"}} '
        f"from the worst areas in the data\n"
        f'  "interventions": array of 3-4 concrete, locally-actionable suggestions tied to the '
        f"drivers (e.g. construction dust control, traffic management at named hotspots)\n"
        f"Ground every number in the data. Be specific and non-generic."
    )
    model = PRO_MODEL
    try:
        rep = generate("vaani", "report", prompt, model=PRO_MODEL, city_id=city_id, as_json=True)
    except Exception as e:  # noqa: BLE001 — Pro quota can be exhausted; fall back to Flash
        print(f"  Pro failed ({type(e).__name__}); falling back to Flash")
        model = FLASH_MODEL
        rep = generate("vaani", "report", prompt, model=FLASH_MODEL, city_id=city_id, as_json=True)
    return _render_html(city.name, ctx, rep, model)


def _render_html(city_name: str, ctx: dict, rep: dict, model: str) -> str:
    e = _html.escape
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    hotspots = "".join(
        f"<tr><td>{e(str(h.get('area','')))}</td><td>{e(str(h.get('forecast_pm25','')))}</td>"
        f"<td>{e(str(h.get('category','')))}</td><td>{e(str(h.get('likely_driver','')))}</td></tr>"
        for h in rep.get("hotspots", [])
    )
    interventions = "".join(f"<li>{e(str(i))}</li>" for i in rep.get("interventions", []))
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{e(rep.get('title', city_name+' Air Quality Report'))}</title>
<style>
 body{{font-family:Georgia,serif;max-width:760px;margin:40px auto;padding:0 20px;color:#1a1a1a;line-height:1.55}}
 h1{{border-bottom:3px solid #1f6feb;padding-bottom:8px}} h2{{color:#1f6feb;margin-top:28px}}
 table{{border-collapse:collapse;width:100%;margin:12px 0}} th,td{{border:1px solid #ccc;padding:8px;text-align:left;font-size:14px}}
 th{{background:#f0f4f8}} .meta{{color:#666;font-size:13px}} .caveat{{background:#fff8e1;border-left:4px solid #f29c33;padding:12px;font-size:13px;margin-top:28px}}
</style></head><body>
<h1>{e(rep.get('title', city_name+' — Weekly Air Quality Briefing'))}</h1>
<p class="meta">For the MP's office · {e(city_name)} · generated {gen} · forecast as of {e(str(ctx.get('as_of')))}</p>
<h2>Executive summary</h2><p>{e(rep.get('exec_summary',''))}</p>
<h2>Tomorrow's outlook</h2><p>{e(rep.get('outlook',''))}</p>
<h2>Top hotspots (next-24h forecast)</h2>
<table><tr><th>Area</th><th>Forecast PM2.5 (µg/m³)</th><th>Category</th><th>Likely driver</th></tr>{hotspots}</table>
<h2>Recommended interventions</h2><ul>{interventions}</ul>
<div class="caveat"><b>Methodology &amp; caveats.</b> Forecasts use a gradient-boosted model on
CAMS-modelled pollutant history (CPCB provides no historical API); they are cross-validated against
live CPCB readings as data accrues. "Likely driver" is a heuristic from weather conditions, not
measured source apportionment. Ward-level detail is interpolated (IDW) from a limited station network —
confidence varies with distance to the nearest station. Model: {e(model)}.</div>
</body></html>"""


def run(city_ids: list[str]) -> int:
    now = pd.Timestamp(datetime.now(timezone.utc))
    rows = []
    for cid in city_ids:
        try:
            html_doc = generate_report(cid)
            rows.append({"city_id": cid, "generated_at": now, "html": html_doc,
                         "model": PRO_MODEL})
            print(f"  {cid}: report generated ({len(html_doc)} chars)")
        except Exception as ex:  # noqa: BLE001
            print(f"  {cid}: FAILED {type(ex).__name__}: {str(ex)[:80]}")
    if rows:
        bq.load_dataframe(pd.DataFrame(rows), "reports", write_disposition="WRITE_APPEND")
        print(f"Wrote {len(rows)} reports.")
    return len(rows)


if __name__ == "__main__":
    run(sys.argv[1:] or ["delhi", "bengaluru"])
