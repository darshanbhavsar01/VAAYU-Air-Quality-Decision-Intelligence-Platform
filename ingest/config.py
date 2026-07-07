"""Central config for VAAYU ingest jobs. Reads from environment / .env.

Nothing sensitive is hard-coded here — keys come from the environment
(local: .env; cloud: Secret Manager injected as env vars).
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Load .env from repo root if present (local dev only).
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # dotenv optional in cloud where env is injected
    pass

# --- Data source keys ---
DATA_GOV_IN_API_KEY = os.getenv("DATA_GOV_IN_API_KEY", "")
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY", "")  # optional now; WAQI is the primary secondary source
WAQI_API_TOKEN = os.getenv("WAQI_API_TOKEN", "")  # https://aqicn.org/data-platform/token/ (instant, no email wait)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- GCP ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
BQ_DATASET = os.getenv("BQ_DATASET", "vaayu")

# --- City targeting ---
# Multi-city is config-driven via config/cities.yaml (see ingest/cities.py).
# CITY_NAME/CITY_STATE below are legacy single-city fallbacks, kept only for
# scripts that haven't been migrated to iterate the registry yet.
CITY_NAME = os.getenv("CITY_NAME", "Bengaluru")
CITY_STATE = os.getenv("CITY_STATE", "Karnataka")

# CPCB CAAQMS real-time resource on data.gov.in (hourly latest snapshot per station).
CPCB_RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
DATA_GOV_IN_BASE = "https://api.data.gov.in/resource"

OPENAQ_BASE = "https://api.openaq.org/v3"

# data.gov.in (and some other endpoints) sit behind a WAF that stalls the
# default "python-requests/x.y" User-Agent — requests hang until timeout while
# curl/browsers get an instant 200. A browser-like UA fixes it. Use HTTP_HEADERS
# on every outbound request in the ingest layer.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VAAYU/0.1 (+air-quality research)"
HTTP_HEADERS = {"User-Agent": USER_AGENT}

# Pollutants VAAYU tracks (CPCB CAAQMS parameter names).
POLLUTANTS = ["PM2.5", "PM10", "NO2", "SO2", "CO", "OZONE"]

# Repo paths
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"


def require(name: str, value: str) -> str:
    """Fail loudly if a required secret is missing."""
    if not value:
        raise SystemExit(
            f"Missing required config: {name}. "
            f"Set it in your .env (see .env.example) or export it in the environment."
        )
    return value
