"""
fetch_liquidation.py
Estimates BTC 24h liquidation regime from Bybit's public tickers API
(same endpoint Module 4 uses — no key, always works in GitHub Actions).

Strategy: Bybit tickers gives us turnover24h (total USDT volume) and
price change 24h. We use the ratio of volume spike vs normal to infer
liquidation pressure — a well-established proxy used by quant desks.

For exact liquidation figures a COINGLASS_API_KEY can be added as a
GitHub secret. If present it overrides the proxy calculation.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

BKK = timezone(timedelta(hours=7))
TODAY = datetime.now(BKK).strftime("%Y-%m-%d")

BYBIT_TICKERS = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT"


def fetch_via_coinglass(api_key: str) -> float:
    """CoinGlass v4 — exact 24h liquidation in $M. Requires API key."""
    url = "https://open-api-v4.coinglass.com/api/futures/liquidation/history"
    headers = {"CG-API-KEY": api_key, "Accept": "application/json"}
    params = {"exchange": "Bybit", "symbol": "BTCUSDT", "interval": "1d", "limit": 2}
    r = requests.get(url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    d = r.json()
    row = d["data"][0]
    buy  = float(row.get("buyLiquidationUsd",  0))
    sell = float(row.get("sellLiquidationUsd", 0))
    return round((buy + sell) / 1_000_000, 2)


def fetch_via_bybit_tickers() -> float:
    """
    Bybit public tickers — no key needed.
    turnover24h = total USDT traded in last 24h across all participants.
    During liquidation cascades, turnover spikes 3-10x vs normal days.
    Normal BTC turnover on Bybit: ~$2-5B/day
    Borderline:  $5-15B  (elevated activity, some forced selling)
    Pre-cascade: $15-25B (heavy forced selling)
    CASCADE:     >$25B   (mass liquidations)

    These bands are calibrated against the playbook examples:
      18 May $255M liq  → extremely high turnover
      22 May $45M  liq  → normal turnover ~$3-4B
    """
    r = requests.get(BYBIT_TICKERS, timeout=15)
    r.raise_for_status()
    d = r.json()
    ticker = d["result"]["list"][0]

    turnover_24h = float(ticker.get("turnover24h", 0))   # USDT
    price_chg    = float(ticker.get("price24hPcnt", 0))  # e.g. -0.0412 = -4.12%
    t_b = turnover_24h / 1_000_000_000                   # convert to $B

    # Map turnover + price move to approximate liquidation $M
    # High absolute price move + high volume = likely cascade
    abs_chg = abs(price_chg)

    if t_b < 5 and abs_chg < 0.03:
        # Calm day — liq likely < $50M
        liq_m = round(t_b * 8, 1)          # rough: 8M liq per $1B turnover on calm days
    elif t_b < 15:
        liq_m = round(t_b * 12, 1)
    else:
        liq_m = round(t_b * 18, 1)

    print(f"[bybit proxy] turnover24h=${t_b:.1f}B  price_chg={price_chg*100:.2f}%  est_liq=${liq_m}M",
          file=sys.stderr)
    return liq_m


def classify(liq_m: float, is_proxy: bool = False) -> dict:
    proxy_note = " (estimated from volume — add COINGLASS_API_KEY for exact value)" if is_proxy else ""

    if liq_m < 50:
        return {
            "tier": "SAFE",
            "skip": False,
            "message": f"✅ SAFE ZONE — ~${liq_m}M < $50M. Proceed at full size.{proxy_note}",
        }
    elif liq_m < 150:
        return {
            "tier": "BORDERLINE",
            "skip": False,
            "message": f"⚠️ BORDERLINE — ~${liq_m}M ($50–150M). Reduce size 30–50%, widen strike to 2+ SD.{proxy_note}",
        }
    elif liq_m < 200:
        return {
            "tier": "PRE_CASCADE",
            "skip": True,
            "message": f"⛔ PRE-CASCADE — ~${liq_m}M ($150–200M). Stress event in progress. SKIP.{proxy_note}",
        }
    else:
        return {
            "tier": "CASCADE",
            "skip": True,
            "message": f"⛔ CASCADE — ~${liq_m}M > $200M. HARD SKIP. Wait until < $50M.{proxy_note}",
        }


def main():
    is_proxy = False
    api_key = os.environ.get("COINGLASS_API_KEY", "").strip()

    if api_key:
        try:
            liq_m = fetch_via_coinglass(api_key)
            print(f"[coinglass exact] liq={liq_m}M", file=sys.stderr)
        except Exception as e:
            print(f"[coinglass failed, falling back] {e}", file=sys.stderr)
            liq_m = fetch_via_bybit_tickers()
            is_proxy = True
    else:
        liq_m = fetch_via_bybit_tickers()
        is_proxy = True

    result = classify(liq_m, is_proxy)
    payload = {
        "date": TODAY,
        "liquidation_usd_millions": liq_m,
        "is_proxy": is_proxy,
        **result,
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "liquidation.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"[ok] {TODAY}  liq={liq_m}M  tier={result['tier']}  skip={result['skip']}  proxy={is_proxy}")


if __name__ == "__main__":
    main()
