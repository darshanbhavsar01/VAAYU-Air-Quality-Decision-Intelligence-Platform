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
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- GCP ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
BQ_DATASET = os.getenv("BQ_DATASET", "vaayu")

# --- City targeting (config-driven; Bengaluru is the pilot city) ---
CITY_NAME = os.getenv("CITY_NAME", "Bengaluru")
CITY_STATE = os.getenv("CITY_STATE", "Karnataka")

# CPCB CAAQMS real-time resource on data.gov.in (hourly latest snapshot per station).
CPCB_RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
DATA_GOV_IN_BASE = "https://api.data.gov.in/resource"

OPENAQ_BASE = "https://api.openaq.org/v3"

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
