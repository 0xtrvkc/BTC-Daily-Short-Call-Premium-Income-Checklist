"""
fetch_liquidation.py
Fetches BTC 24h liquidation total from CoinGlass v4 API and writes
data/liquidation.json — consumed by Module 6B in index.html.
Requires COINGLASS_API_KEY environment variable / GitHub secret.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
import requests

BKK = timezone(timedelta(hours=7))
TODAY = datetime.now(BKK).strftime("%Y-%m-%d")

BASE = "https://open-api-v4.coinglass.com"


def get(path, api_key, params=None):
    headers = {"CG-API-KEY": api_key, "Accept": "application/json"}
    r = requests.get(f"{BASE}{path}", headers=headers, params=params or {}, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_liquidation_usd(api_key: str) -> float:
    # Try the coin-list endpoint first — most likely to have 24h totals
    try:
        d = get("/api/futures/liquidation/coin-list", api_key)
        print(f"[coin-list] {json.dumps(d)[:500]}", file=sys.stderr)
        for item in d.get("data", []):
            if item.get("symbol") == "BTC":
                # Try every plausible field name
                for field in ["liquidationUsd24h", "liquidation24h", "h24LiquidationUsd",
                              "liqUsd24h", "liquidationUsd", "totalLiquidationUsd"]:
                    if field in item:
                        return round(float(item[field]) / 1_000_000, 2)
                # If no known field, print all keys so we can fix it
                print(f"[coin-list BTC fields] {json.dumps(item)}", file=sys.stderr)
    except Exception as e:
        print(f"[coin-list failed] {e}", file=sys.stderr)

    # Try the aggregated history endpoint — last 1d bar
    try:
        d = get("/api/futures/liquidation/history", api_key,
                params={"symbol": "BTC", "interval": "1d", "limit": 1})
        print(f"[history] {json.dumps(d)[:500]}", file=sys.stderr)
        rows = d.get("data", [])
        if rows:
            row = rows[0]
            buy  = float(row.get("buyLiquidationUsd",  row.get("longLiqUsd",  0)))
            sell = float(row.get("sellLiquidationUsd", row.get("shortLiqUsd", 0)))
            total = buy + sell
            if total > 0:
                return round(total / 1_000_000, 2)
            print(f"[history BTC row fields] {json.dumps(row)}", file=sys.stderr)
    except Exception as e:
        print(f"[history failed] {e}", file=sys.stderr)

    raise RuntimeError("Could not parse liquidation from any endpoint — check stderr for field names.")


def classify(liq_m: float) -> dict:
    if liq_m < 50:
        return {"tier": "SAFE",       "skip": False,
                "message": f"✅ SAFE ZONE — ${liq_m}M < $50M. Proceed at full size."}
    elif liq_m < 150:
        return {"tier": "BORDERLINE", "skip": False,
                "message": f"⚠️ BORDERLINE — ${liq_m}M ($50–150M). Reduce size 30–50%, widen strike to 2+ SD."}
    elif liq_m < 200:
        return {"tier": "PRE_CASCADE","skip": True,
                "message": f"⛔ PRE-CASCADE — ${liq_m}M ($150–200M). Stress event in progress. SKIP."}
    else:
        return {"tier": "CASCADE",    "skip": True,
                "message": f"⛔ CASCADE — ${liq_m}M > $200M. HARD SKIP. Wait until < $50M."}


def main():
    api_key = os.environ.get("COINGLASS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("COINGLASS_API_KEY secret is not set.")

    liq_m  = fetch_liquidation_usd(api_key)
    result = classify(liq_m)
    payload = {"date": TODAY, "liquidation_usd_millions": liq_m, **result}

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "liquidation.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[ok] {TODAY}  liq={liq_m}M  tier={result['tier']}  skip={result['skip']}")


if __name__ == "__main__":
    main()
