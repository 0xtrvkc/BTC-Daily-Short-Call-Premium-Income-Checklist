"""
check_macro.py
Scrapes ForexFactory for today's HIGH impact USD events.
Writes result to /data/macro.json.
Runs via GitHub Actions every morning before 8am Bangkok (GMT+7).
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
BANGKOK_TZ   = timezone(timedelta(hours=7))
OUTPUT_PATH  = Path(__file__).parent.parent / "data" / "macro.json"
FF_URL       = "https://www.forexfactory.com/calendar"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def today_bangkok() -> str:
    """Return today's date string in Bangkok time: YYYY-MM-DD"""
    return datetime.now(BANGKOK_TZ).strftime("%Y-%m-%d")


def scrape_events() -> list[dict]:
    """
    Fetch ForexFactory calendar and return list of HIGH impact USD events.
    Each item: { time, currency, impact, event }
    """
    resp = requests.get(FF_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    table = soup.find("table", class_="calendar__table")
    if not table:
        raise RuntimeError("Could not find calendar table — ForexFactory layout may have changed.")

    current_time = ""  # FF omits time cell when multiple events share a time slot

    for row in table.find_all("tr", class_=re.compile(r"calendar__row")):
        # Skip header / separator rows
        if "calendar__row--day-breaker" in row.get("class", []):
            break  # past today's section into tomorrow — stop

        # Time cell (may be empty if shared)
        time_cell = row.find("td", class_="calendar__time")
        if time_cell and time_cell.get_text(strip=True):
            current_time = time_cell.get_text(strip=True)

        # Currency
        currency_cell = row.find("td", class_="calendar__currency")
        if not currency_cell:
            continue
        currency = currency_cell.get_text(strip=True)
        if currency != "USD":
            continue

        # Impact — FF uses a <span> with class like "icon--ff-impact-red"
        impact_cell = row.find("td", class_="calendar__impact")
        if not impact_cell:
            continue
        impact_span = impact_cell.find("span")
        if not impact_span:
            continue
        impact_classes = " ".join(impact_span.get("class", []))
        if "red" not in impact_classes.lower():
            continue  # not HIGH impact

        # Event name
        event_cell = row.find("td", class_="calendar__event")
        if not event_cell:
            continue
        event_name = event_cell.get_text(strip=True)

        events.append({
            "time": current_time,
            "currency": currency,
            "impact": "HIGH",
            "event": event_name,
        })

    return events


def build_result(events: list[dict]) -> dict:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    skip = len(events) > 0
    return {
        "date": today_bangkok(),
        "checked_at": now_utc,
        "skip": skip,
        "event_count": len(events),
        "events": events,
        "summary": (
            f"{len(events)} HIGH impact USD event(s) found — SKIP TRADE"
            if skip
            else "No HIGH impact USD events — PROCEED"
        ),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Checking ForexFactory for {today_bangkok()} (Bangkok time)...")

    try:
        events = scrape_events()
    except Exception as exc:
        # Write a safe fallback — don't block the checklist, but flag it
        result = {
            "date": today_bangkok(),
            "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skip": False,
            "event_count": 0,
            "events": [],
            "summary": f"⚠️ Scrape failed: {exc} — verify manually",
            "error": str(exc),
        }
        print(f"ERROR: {exc}")
    else:
        result = build_result(events)
        print(f"Found {len(events)} HIGH impact USD event(s).")
        for e in events:
            print(f"  [{e['time']}] {e['event']}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2))
    print(f"Written → {OUTPUT_PATH}")

    # Exit code 0 always — let the checklist HTML decide what to show
    # (non-zero exit would fail the GH Action and skip the commit step)


if __name__ == "__main__":
    main()
