"""
fetch_liquidation.py
Fetches BTC 24h liquidation total from CoinGlass API and writes
data/liquidation.json — consumed by Module 6B in index.html.

Mirrors the pattern of fetch_macro.py (Module 1).
Run via GitHub Actions on a schedule.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

# ── Bangkok time (UTC+7) ──────────────────────────────────────────────────────
BKK = timezone(timedelta(hours=7))
TODAY = datetime.now(BKK).strftime("%Y-%m-%d")

# ── CoinGlass public endpoint ─────────────────────────────────────────────────
# Returns the same data shown in the Derivatives row of coinglass.com
URL = "https://open-api.coinglass.com/public/v2/liquidation_ex"
HEADERS = {
    "accept": "application/json",
    "coinglassSecret": os.environ.get("COINGLASS_API_KEY", ""),
}

# Fallback: use the free /futures/liquidation/info endpoint (no key needed)
URL_FREE = "https://open-api.coinglass.com/api/futures/liquidation/info?symbol=BTC&time_type=h24"
HEADERS_FREE = {"accept": "application/json"}


def fetch_liquidation_usd() -> float:
    """Return BTC 24h total liquidation in USD (millions)."""

    # Try free endpoint first (no API key required)
    try:
        r = requests.get(URL_FREE, headers=HEADERS_FREE, timeout=15)
        r.raise_for_status()
        d = r.json()
        # Response: {"data": {"liquidationUsd": 409760000, ...}}
        liq_usd = float(d["data"]["liquidationUsd"])
        return round(liq_usd / 1_000_000, 2)   # convert to millions
    except Exception as e:
        print(f"[free endpoint failed] {e}", file=sys.stderr)

    # Fallback: use the open API with secret key
    api_key = os.environ.get("COINGLASS_API_KEY", "")
    if api_key:
        try:
            params = {"symbol": "BTC", "timeType": "h24"}
            r = requests.get(URL, headers=HEADERS, params=params, timeout=15)
            r.raise_for_status()
            d = r.json()
            liq_usd = float(d["data"][0]["liquidationUsd"])
            return round(liq_usd / 1_000_000, 2)
        except Exception as e:
            print(f"[api endpoint failed] {e}", file=sys.stderr)

    raise RuntimeError("All CoinGlass endpoints failed — check network or API key.")


def classify(liq_m: float) -> dict:
    """Return tier classification and message for a given liquidation in $M."""
    if liq_m < 50:
        return {
            "tier": "SAFE",
            "skip": False,
            "message": f"✅ SAFE ZONE — ${liq_m}M < $50M. Proceed at full size.",
        }
    elif liq_m < 150:
        return {
            "tier": "BORDERLINE",
            "skip": False,
            "message": f"⚠️ BORDERLINE — ${liq_m}M ($50–150M range). Reduce size 30–50%, widen strike to 2+ SD.",
        }
    elif liq_m < 200:
        return {
            "tier": "PRE_CASCADE",
            "skip": True,
            "message": f"⛔ PRE-CASCADE — ${liq_m}M ($150–200M). Stress event in progress. SKIP.",
        }
    else:
        return {
            "tier": "CASCADE",
            "skip": True,
            "message": f"⛔ CASCADE — ${liq_m}M > $200M threshold. HARD SKIP. Wait until < $50M.",
        }


def main():
    liq_m = fetch_liquidation_usd()
    result = classify(liq_m)

    payload = {
        "date": TODAY,
        "liquidation_usd_millions": liq_m,
        **result,
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "liquidation.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"[ok] {TODAY}  liq={liq_m}M  tier={result['tier']}  skip={result['skip']}")


if __name__ == "__main__":
    main()
