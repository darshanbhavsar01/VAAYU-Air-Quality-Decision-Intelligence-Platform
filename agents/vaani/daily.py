"""vaani daily job — regenerate advisories + weekly reports once per day.

Runs on a DAILY Cloud Scheduler cadence (not hourly) to respect the Gemini
free-tier daily quota. Advisories upsert + skip-existing, so even a partial run
under rate limits accumulates coverage across days. Reports are generated for
the highest-signal cities.

Run: python agents/vaani/daily.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "ingest"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import advisory  # noqa: E402
import report  # noqa: E402

# Report cities: most decision-relevant (Delhi breaches; Bengaluru is primary demo).
REPORT_CITIES = ["delhi", "bengaluru"]


def main() -> None:
    print("[vaani] generating advisories (upsert, skip-existing)...", flush=True)
    try:
        advisory.run(skip_existing=True)
    except Exception as e:  # noqa: BLE001
        print(f"[vaani] advisories step error (non-fatal): {type(e).__name__}: {e}", flush=True)
    print("[vaani] generating weekly reports...", flush=True)
    try:
        report.run(REPORT_CITIES)
    except Exception as e:  # noqa: BLE001
        print(f"[vaani] reports step error (non-fatal): {type(e).__name__}: {e}", flush=True)
    print("[vaani] daily done.", flush=True)


if __name__ == "__main__":
    main()
