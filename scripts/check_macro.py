"""
check_macro.py
Scrapes ForexFactory for today's HIGH impact USD events.
Only triggers skip for FOMC / CPI / NFP / Fed Chair / Fed Speech.
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

# Only these events trigger a skip — everything else (ISM, PMI, etc.) is ignored
KILL_LIST = ["FOMC", "CPI", "NFP", "Fed Chair", "Fed Speech", "Federal Reserve", "PPI m/m", "Core PPI m/m", "Non-Farm", "Unemployment", "Earnings m/m"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def today_bangkok() -> str:
    return datetime.now(BANGKOK_TZ).strftime("%Y-%m-%d")


def today_ff_label() -> str:
    """
    ForexFactory day-breaker rows contain text like 'Mon Jun 1' or 'Jun 1'.
    Returns e.g. 'Jun 1'
    """
    now = datetime.now(BANGKOK_TZ)
    return now.strftime("%b %-d")


def is_red_impact(impact_cell) -> bool:
    """FF uses <span class="icon icon--ff-impact-red"> for HIGH impact."""
    if not impact_cell:
        return False
    for tag in impact_cell.find_all(True):
        classes = " ".join(tag.get("class", []))
        if "icon--ff-impact-red" in classes:
            return True
    return False


def is_on_kill_list(event_name: str) -> bool:
    """Return True if the event name matches any entry in KILL_LIST."""
    return any(k.lower() in event_name.lower() for k in KILL_LIST)


def scrape_events() -> list[dict]:
    resp = requests.get(FF_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", class_="calendar__table")
    if not table:
        snippet = resp.text[5000:8000]
        print(f"DEBUG: calendar__table not found. HTML snippet:\n{snippet}")
        raise RuntimeError("Could not find calendar table — layout may have changed.")

    today_label = today_ff_label()
    print(f"DEBUG: looking for day label containing '{today_label}'")

    events           = []
    current_time     = ""
    in_today_section = False

    for row in table.find_all("tr", class_=re.compile(r"calendar__row")):
        row_classes = row.get("class", [])

        # ── Day-breaker: match by date text, not by count ──
        if "calendar__row--day-breaker" in row_classes:
            breaker_text = row.get_text(strip=True)
            print(f"DEBUG day-breaker: '{breaker_text}'")

            if today_label in breaker_text:
                in_today_section = True
                continue

            if in_today_section:
                print(f"DEBUG: hit tomorrow's day-breaker '{breaker_text}', stopping")
                break

            continue

        if not in_today_section:
            continue

        # Time
        time_cell = row.find("td", class_="calendar__time")
        if time_cell and time_cell.get_text(strip=True):
            current_time = time_cell.get_text(strip=True)

        # Currency — must be USD
        currency_cell = row.find("td", class_="calendar__currency")
        if not currency_cell:
            continue
        currency = currency_cell.get_text(strip=True)
        if currency != "USD":
            continue

        # Event name — get it early so we can kill-list check
        event_cell = row.find("td", class_="calendar__event")
        if not event_cell:
            continue
        event_name = event_cell.get_text(strip=True)

        # Impact — must be red AND on kill list
        impact_cell = row.find("td", class_="calendar__impact")
        red      = is_red_impact(impact_cell)
        on_list  = is_on_kill_list(event_name)
        print(f"DEBUG row: time={current_time} currency={currency} "
              f"red={red} on_kill_list={on_list} event='{event_name}'")

        if not (red and on_list):
            continue

        print(f"  ✅ KILL LIST match: [{current_time}] {event_name}")
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
            f"{len(events)} kill-list event(s) found — SKIP TRADE"
            if skip
            else "No FOMC/CPI/NFP/Fed Speech today — PROCEED"
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
        print(f"Found {len(events)} kill-list event(s).")
        for e in events:
            print(f"  [{e['time']}] {e['event']}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2))
    print(f"Written → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
