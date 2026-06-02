"""
fetch_m7.py — Module 7 Delta Selection
Fetches today's BTC daily expiry from Bybit options API,
finds the strike with delta closest to 0.13–0.15, writes data/m7.json
"""
import json, math, requests
from datetime import datetime, timezone

def get_today_expiry():
    # Bybit daily options expire at 08:00 UTC
    now = datetime.now(timezone.utc)
    # Format: 19MAY25
    return now.strftime("%-d%b%y").upper()  # e.g. "2JUN26"

def fetch_m7():
    expiry = get_today_expiry()
    url = "https://api.bybit.com/v5/market/tickers"
    params = {"category": "option", "baseCoin": "BTC", "expDate": expiry}

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    tickers = r.json()["result"]["list"]

    # Filter Call options only
    calls = [t for t in tickers if t["symbol"].endswith("-C")]

    # Get spot price from any ticker
    spot = float(calls[0]["underlyingPrice"]) if calls else None

    # Find strikes with delta in 0.10–0.20 range, pick closest to 0.14
    best = None
    best_dist = 99
    candidates = []

    for t in calls:
        delta = abs(float(t.get("delta", 0) or 0))
        if 0.10 <= delta <= 0.20:
            strike = float(t["symbol"].split("-")[2])
            iv = round(float(t.get("markIv", 0) or 0) * 100, 1)
            premium = float(t.get("lastPrice", 0) or 0)
            dist_from_spot_pct = round((strike - spot) / spot * 100, 2) if spot else None
            candidates.append({
                "strike": strike,
                "delta": round(delta, 4),
                "iv": iv,
                "premium": premium,
                "dist_pct": dist_from_spot_pct
            })
            d = abs(delta - 0.14)
            if d < best_dist:
                best_dist = d
                best = candidates[-1]

    # Determine recommendation
    if best is None:
        result = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "expiry": expiry,
            "spot": spot,
            "found": False,
            "autoCheck": False,
            "autoSkip": False,
            "result": "No delta 0.13–0.15 strike found — check Bybit manually",
            "detail": "Bybit returned no option tickers for today's expiry in the target delta range."
        }
    else:
        delta = best["delta"]
        iv = best["iv"]
        strike = best["strike"]
        dist = best["dist_pct"]

        in_range = 0.13 <= delta <= 0.15
        recommend_delta = 0.10 if iv > 60 else 0.15
        too_close = dist is not None and dist < 1.5

        if in_range and not too_close:
            summary = f"✅ Strike ${int(strike):,} | Delta {delta} | IV {iv}% | +{dist}% above spot"
            detail = (
                f"Found delta {delta} strike at ${int(strike):,}, {dist}% above spot ${int(spot):,}. "
                f"IV is {iv}%. This is within the 0.13–0.15 sweet spot with ~85% win probability. "
                f"Use this strike."
            )
            auto_check = True
            auto_skip = False
        elif iv > 60:
            summary = f"⚠️ IV={iv}% (>60%) — use delta 0.10 strike instead of 0.15"
            detail = (
                f"IV is elevated at {iv}%, above the 60% threshold. "
                f"Best delta 0.15 strike is ${int(strike):,} (+{dist}% from spot). "
                f"Recommend moving to delta 0.10 for safety — still good premium in high-IV regime."
            )
            auto_check = True
            auto_skip = False
        elif too_close:
            summary = f"⚠️ Strike ${int(strike):,} only +{dist}% above spot — too close (low IV)"
            detail = (
                f"Delta {delta} strike is ${int(strike):,}, only {dist}% above spot ${int(spot):,}. "
                f"IV={iv}% is low, meaning the delta 0.15 strike sits very close to spot. "
                f"Premium may not justify the risk. Consider skipping or using delta 0.10."
            )
            auto_check = False
            auto_skip = False
        else:
            summary = f"🟡 Strike ${int(strike):,} | Delta {delta} | borderline range"
            detail = (
                f"Closest strike to delta 0.14 is ${int(strike):,} with delta {delta}, "
                f"{dist}% above spot. IV={iv}%. Borderline — check manually."
            )
            auto_check = False
            auto_skip = False

        result = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "expiry": expiry,
            "spot": spot,
            "found": True,
            "strike": strike,
            "delta": delta,
            "iv": iv,
            "premium": best["premium"],
            "dist_pct": dist,
            "recommend_delta": recommend_delta,
            "candidates": candidates,
            "autoCheck": auto_check,
            "autoSkip": auto_skip,
            "result": summary,
            "detail": detail
        }

    with open("data/m7.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"[m7] Written: {result['result']}")

if __name__ == "__main__":
    fetch_m7()
