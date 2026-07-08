"""Shared Gemini/agent plumbing for VAAYU's three agents (CLAUDE.md §7).

- Calls the Gemini API via the AI Studio key (generativelanguage.googleapis.com,
  `google-genai` SDK) — NOT Vertex AI (keeps model usage off the GCP bill).
- Every call gets a grounding system instruction ("answer only from provided
  data") and is logged to BigQuery `agent_logs` for audit + free-tier volume
  tracking. No agent writes to raw_* tables.
- Flash for advisories/ask; Pro reserved for the weekly report.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google import genai
from google.genai import errors, types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))
import bq  # noqa: E402

# gemini-2.5-flash free tier is only 20 requests/DAY — one advisory generation
# (7 cities × ~3 langs) exhausts it. flash-lite has a far larger free daily
# quota and is plenty for short advisories. Pro reserved for the weekly report.
FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash-lite")
PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")

GROUNDING = (
    "You are a careful assistant for a government air-quality platform. "
    "Answer ONLY from the structured data provided in the prompt. Do not invent "
    "numbers, station names, places, or trends that are not in the data. If the "
    "data does not support an answer, say so plainly. Be concise and factual."
)

_client: genai.Client | None = None


def client() -> genai.Client:
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise SystemExit("Missing GEMINI_API_KEY (AI Studio key). Set it in .env / Secret Manager.")
        _client = genai.Client(api_key=key)  # AI Studio (generativelanguage), not Vertex
    return _client


def _log(agent: str, task: str, model: str, city_id: str | None, lang: str | None,
         prompt: str, response: str, latency_ms: int, ok: bool, error: str | None) -> None:
    import pandas as pd
    row = pd.DataFrame([{
        "agent": agent, "task": task, "model": model, "city_id": city_id, "lang": lang,
        "prompt_chars": len(prompt), "response_chars": len(response),
        "latency_ms": latency_ms, "ok": ok, "error": error,
        "ts": pd.Timestamp(datetime.now(timezone.utc)),
    }])
    try:
        bq.load_dataframe(row, "agent_logs", write_disposition="WRITE_APPEND")
    except Exception as e:  # noqa: BLE001 — logging must never break the agent
        print(f"[agent_logs] failed to log: {e}", flush=True)


def generate(agent: str, task: str, prompt: str, *, model: str | None = None,
             system: str = GROUNDING, city_id: str | None = None, lang: str | None = None,
             as_json: bool = False, schema: Any = None) -> str | dict:
    """Call Gemini with grounding + audit logging. Returns text, or a parsed
    dict when as_json=True."""
    model = model or FLASH_MODEL
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.3,
        response_mime_type="application/json" if as_json else "text/plain",
        response_schema=schema,
    )
    t = time.time()
    text, ok, err = "", True, None
    try:
        text = _generate_with_retry(model, prompt, cfg)
    except Exception as e:  # noqa: BLE001
        ok, err = False, f"{type(e).__name__}: {e}"
        raise
    finally:
        _log(agent, task, model, city_id, lang, prompt, text, int((time.time() - t) * 1000), ok, err)
    return json.loads(_strip_fences(text)) if as_json else text


def _generate_with_retry(model: str, prompt: str, cfg: Any, tries: int = 5) -> str:
    """Retry transient Gemini errors (503 overload, 429 rate limit) with backoff."""
    for i in range(tries):
        try:
            resp = client().models.generate_content(model=model, contents=prompt, config=cfg)
            return resp.text or ""
        except (errors.ServerError, errors.ClientError) as e:
            code = getattr(e, "code", None)
            if code in (429, 500, 503) and i < tries - 1:
                time.sleep(2.0 * (2 ** i))  # 2,4,8,16s
                continue
            raise
    return ""


def _strip_fences(text: str) -> str:
    """Gemini sometimes wraps JSON in ```json ... ``` fences even in JSON mode."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()
