"""oracle — forecast & attribution Q&A (CLAUDE.md §7.2).

Answers natural-language questions for the MP dashboard's "Ask VAAYU" box,
grounded strictly in a compact BigQuery snapshot (no arbitrary SQL generation —
safe and hallucination-resistant). The snapshot covers every city's next-24h
forecast outlook + worst areas + feed health, so it handles both single-city
("what's the forecast for Delhi?") and comparative ("compare Delhi and Mumbai",
"which cities breach tomorrow?") questions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "ingest"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bq  # noqa: E402
from common import generate  # noqa: E402

_CTX_CACHE: dict | None = None


def build_context() -> dict:
    """Compact all-cities forecast snapshot the model may answer from."""
    sql = f"""
    WITH sf AS (
      SELECT sf.*, c.name AS city_name
      FROM `{bq.table_fqn('station_forecast')}` sf
      JOIN `{bq.table_fqn('cities')}` c USING (city_id)
    )
    SELECT
      city_id, ANY_VALUE(city_name) AS city_name,
      ROUND(MAX(pred_max_pm25_24h), 1) AS predicted_max_pm25,
      ROUND(AVG(breach_prob), 3) AS avg_breach_prob,
      COUNTIF(pred_breach_naaqs) AS stations_breaching,
      COUNT(*) AS n_stations,
      MAX(as_of) AS as_of,
      ARRAY_AGG(STRUCT(station AS area, ROUND(pred_max_pm25_24h,1) AS pm25, pred_category)
                ORDER BY pred_max_pm25_24h DESC LIMIT 3) AS worst_areas
    FROM sf GROUP BY city_id
    ORDER BY predicted_max_pm25 DESC
    """
    rows = [dict(r) for r in bq.client().query(sql, location=bq.BQ_LOCATION).result()]
    for r in rows:
        r["as_of"] = r["as_of"].isoformat() if r["as_of"] else None
        r["worst_areas"] = [dict(w) for w in r["worst_areas"]]
    return {
        "explanation": "Next-24h PM2.5 forecast per city (CAMS-modelled; India NAAQS "
                       "24h safe limit = 60 µg/m³). 'breach' = predicted max exceeds 60.",
        "cities": rows,
    }


def ask(question: str, refresh: bool = False) -> dict:
    global _CTX_CACHE
    if _CTX_CACHE is None or refresh:
        _CTX_CACHE = build_context()
    prompt = (
        f"Air-quality forecast data (the ONLY facts you may use):\n"
        f"{json.dumps(_CTX_CACHE, ensure_ascii=False, indent=2)}\n\n"
        f"Question: {question}\n\n"
        f"Answer concisely for a Member of Parliament's office. Use the numbers "
        f"from the data. If the data cannot answer it, say so plainly."
    )
    answer = generate("oracle", "ask", prompt, city_id=None)
    return {"question": question, "answer": answer}


if __name__ == "__main__":
    import sys as _s
    q = " ".join(_s.argv[1:]) or "Which cities are forecast to breach the safe limit tomorrow, and which is worst?"
    print(ask(q)["answer"])
