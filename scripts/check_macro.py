"""
check_macro.py
Scrapes ForexFactory for today's HIGH impact USD events.
Writes result to /data/macro.json.
Runs via GitHub Actions every morning before 8am Bangkok (GMT+7).
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
BANGKOK_TZ  = timezone(timedelta(hours=7))
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "macro.json"
FF_URL      = "https://www.forexfactory.com/calendar"

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
    return datetime.now(BANGKOK_TZ).strftime("%Y-%m-%d")


def today_ff_label() -> str:
    """
    ForexFactory day-breaker rows contain text like 'Mon Jun 1' or 'Jun 1'.
    Build both short forms to match against.
    Returns e.g. 'Jun 1'
    """
    now = datetime.now(BANGKOK_TZ)
    # e.g. "Jun 1"  (no leading zero — FF omits it)
    return now.strftime("%b %-d")


def is_high_impact(impact_cell) -> bool:
    """FF uses <span class="icon icon--ff-impact-red"> for HIGH impact."""
    if not impact_cell:
        return False
    for tag in impact_cell.find_all(True):
        classes = " ".join(tag.get("class", []))
        if "icon--ff-impact-red" in classes:
            return True
    return False


def scrape_events() -> list[dict]:
    resp = requests.get(FF_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", class_="calendar__table")
    if not table:
        snippet = resp.text[5000:8000]
        print(f"DEBUG: calendar__table not found. HTML snippet:\n{snippet}")
        raise RuntimeError("Could not find calendar table — layout may have changed.")

    today_label = today_ff_label()   # e.g. "Jun 1"
    print(f"DEBUG: looking for day label containing '{today_label}'")

    events            = []
    current_time      = ""
    in_today_section  = False

    for row in table.find_all("tr", class_=re.compile(r"calendar__row")):
        row_classes = row.get("class", [])

        # ── Day-breaker: check if this row's text matches today or tomorrow ──
        if "calendar__row--day-breaker" in row_classes:
            breaker_text = row.get_text(strip=True)
            print(f"DEBUG day-breaker: '{breaker_text}'")

            if today_label in breaker_text:
                # This is today's header — start collecting
                in_today_section = True
                continue

            if in_today_section:
                # We were in today's section and hit a NEW day — stop
                print(f"DEBUG: hit tomorrow's day-breaker '{breaker_text}', stopping")
                break

            # Haven't reached today yet — skip
            continue

        if not in_today_section:
            continue

        # Time
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

        # Impact
        impact_cell = row.find("td", class_="calendar__impact")
        high = is_high_impact(impact_cell)
        print(f"DEBUG row: time={current_time} currency={currency} high={high} "
              f"impact_html={str(impact_cell)[:120]}")

        if not high:
            continue

        # Event name
        event_cell = row.find("td", class_="calendar__event")
        if not event_cell:
            continue
        event_name = event_cell.get_text(strip=True)

        print(f"  ✅ HIGH impact: [{current_time}] {event_name}")
        events.append({
            "time":     current_time,
            "currency": currency,
            "impact":   "HIGH",
            "event":    event_name,
        })

    return events


def build_result(events: list[dict]) -> dict:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    skip    = len(events) > 0
    return {
        "date":        today_bangkok(),
        "checked_at":  now_utc,
        "skip":        skip,
        "event_count": len(events),
        "events":      events,
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
        result = {
            "date":        today_bangkok(),
            "checked_at":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skip":        False,
            "event_count": 0,
            "events":      [],
            "summary":     f"⚠️ Scrape failed: {exc} — verify manually",
            "error":       str(exc),
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


if __name__ == "__main__":
    main()
