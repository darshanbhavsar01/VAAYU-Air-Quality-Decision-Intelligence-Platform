"""Shared Gemini/agent plumbing for VAAYU's three agents (CLAUDE.md §7).

- Calls the Gemini API via AI Studio keys (generativelanguage.googleapis.com,
  `google-genai` SDK) — NOT Vertex AI (keeps model usage off the GCP bill).
- Every call gets a grounding system instruction ("answer only from provided
  data") and is logged to BigQuery `agent_logs` for audit + free-tier volume
  tracking. No agent writes to raw_* tables.

Free-tier quota reality (see docs/LIMITATIONS.md): each model has its own
small daily/per-minute quota, PER ACCOUNT. A single advisory generation run
(7 cities × ~3 languages) can exhaust one model on one account. So `generate()`
cascades through a list of models on the current account first (2.5-flash ->
2.5-flash-lite -> 2.0-flash -> ... -> 3.5-flash), and only once every model on
that account is exhausted does it move to the next fallback AI Studio account
(a separate key = a separate quota pool entirely). This is the cheapest way to
get more free daily capacity without spending anything.
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

# --- Model cascades -----------------------------------------------------
# Order = preference order. Cheaper/faster models first; each entry is tried
# on the CURRENT account before moving to the next account (see KEYS below).
# Verified live against the AI Studio /models list (2026-07-08) — all of these
# actually exist and accept generateContent.
FLASH_CASCADE: list[str] = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-flash-latest",  # alias safety net — whatever Google currently routes "latest" to
]
PRO_CASCADE: list[str] = [
    "gemini-2.5-pro",
    "gemini-pro-latest",
    "gemini-3-pro-preview",
    "gemini-3.1-pro-preview",
]

# Back-compat constants (first/preferred choice; actual calls cascade beyond these).
FLASH_MODEL = FLASH_CASCADE[0]
PRO_MODEL = PRO_CASCADE[0]

# --- API key fallback chain ---------------------------------------------
# Each key is a DIFFERENT AI Studio account/project -> independent free-tier
# quota pool. Only non-empty keys are used; order = try order.
_KEY_ENV_VARS = ["GEMINI_API_KEY", "GEMINI_API_KEY_FALLBACK1", "GEMINI_API_KEY_FALLBACK2"]


def _keys() -> list[tuple[str, str]]:
    out = []
    for i, var in enumerate(_KEY_ENV_VARS):
        val = os.getenv(var, "")
        if val:
            name = "primary" if i == 0 else f"fallback{i}"
            out.append((name, val))
    if not out:
        raise SystemExit("No Gemini API key configured. Set GEMINI_API_KEY in .env / Secret Manager.")
    return out


GROUNDING = (
    "You are a careful assistant for a government air-quality platform. "
    "Answer ONLY from the structured data provided in the prompt. Do not invent "
    "numbers, station names, places, or trends that are not in the data. If the "
    "data does not support an answer, say so plainly. Be concise and factual."
)

_clients: dict[str, genai.Client] = {}
# (key_name, model) pairs known exhausted/broken THIS PROCESS — skip them
# without re-attempting. Reset naturally on the next container/process start
# (daily Cloud Run Job = fresh process = fresh assumption each day).
_exhausted: set[tuple[str, str]] = set()
# Last (key_name, model) that actually served a request — for logging/inspection.
LAST_USED: tuple[str, str] | None = None


def _client_for(key_name: str, key_value: str) -> genai.Client:
    if key_name not in _clients:
        _clients[key_name] = genai.Client(api_key=key_value)
    return _clients[key_name]


def client() -> genai.Client:
    """Back-compat: the primary account's client."""
    name, key = _keys()[0]
    return _client_for(name, key)


def _log(agent: str, task: str, model: str, key_name: str, city_id: str | None, lang: str | None,
         prompt: str, response: str, latency_ms: int, ok: bool, error: str | None) -> None:
    import pandas as pd
    row = pd.DataFrame([{
        "agent": agent, "task": task, "model": model, "key_name": key_name,
        "city_id": city_id, "lang": lang,
        "prompt_chars": len(prompt), "response_chars": len(response),
        "latency_ms": latency_ms, "ok": ok, "error": error,
        "ts": pd.Timestamp(datetime.now(timezone.utc)),
    }])
    try:
        bq.load_dataframe(row, "agent_logs", write_disposition="WRITE_APPEND")
    except Exception as e:  # noqa: BLE001 — logging must never break the agent
        print(f"[agent_logs] failed to log: {e}", flush=True)


def generate(agent: str, task: str, prompt: str, *, tier: str = "flash", model: str | None = None,
             system: str = GROUNDING, city_id: str | None = None, lang: str | None = None,
             as_json: bool = False, schema: Any = None) -> str | dict:
    """Call Gemini with model+account fallback, grounding, and audit logging.

    tier: "flash" (default; advisories/ask) or "pro" (reports — cascades through
    PRO_CASCADE first, then falls back to FLASH_CASCADE rather than giving up).
    `model`: pin to one specific model (skips cascading) — rarely needed.
    Returns text, or a parsed dict when as_json=True.
    """
    cascade = [model] if model else (PRO_CASCADE + FLASH_CASCADE if tier == "pro" else FLASH_CASCADE)
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.3,
        response_mime_type="application/json" if as_json else "text/plain",
        response_schema=schema,
    )

    global LAST_USED
    last_err: Exception | None = None
    for key_name, key_value in _keys():
        for m in cascade:
            if (key_name, m) in _exhausted:
                continue
            t = time.time()
            text, ok, err = "", True, None
            try:
                text = _generate_with_retry(_client_for(key_name, key_value), m, prompt, cfg)
                LAST_USED = (key_name, m)
                _log(agent, task, m, key_name, city_id, lang, prompt, text,
                     int((time.time() - t) * 1000), True, None)
                return json.loads(_strip_fences(text)) if as_json else text
            except Exception as e:  # noqa: BLE001
                ok, err = False, f"{type(e).__name__}: {e}"
                last_err = e
                code = getattr(e, "code", None)
                if code in (429, 400, 404) or isinstance(e, errors.ClientError):
                    _exhausted.add((key_name, m))  # quota/permission/unknown-model — don't retry this combo again
                _log(agent, task, m, key_name, city_id, lang, prompt, text,
                     int((time.time() - t) * 1000), False, err)
                continue
    raise RuntimeError(f"All Gemini models/accounts exhausted for {agent}/{task}") from last_err


def _generate_with_retry(gclient: genai.Client, model: str, prompt: str, cfg: Any, tries: int = 2) -> str:
    """Short retry for transient errors (e.g. one-off 503) on a SINGLE model+key
    before generate() gives up on this combo and moves to the next one in the
    cascade — kept short since there are many fallback combos to lean on."""
    for i in range(tries):
        try:
            resp = gclient.models.generate_content(model=model, contents=prompt, config=cfg)
            return resp.text or ""
        except errors.ServerError as e:
            if i < tries - 1:
                time.sleep(2.0 * (2 ** i))
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
