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


def is_high_impact(impact_cell) -> bool:
    """
    Return True if the impact cell contains any indicator of HIGH/red impact.
    FF uses several possible patterns — check all of them.
    """
    if not impact_cell:
        return False

    # Stringify the entire cell HTML for broad matching
    cell_html = str(impact_cell).lower()

    # Pattern 1: class contains 'red' anywhere (icon--ff-impact-red, impact-red, etc.)
    if "red" in cell_html:
        return True

    # Pattern 2: title/aria attribute says "High Impact"
    if "high" in cell_html:
        return True

    # Pattern 3: any span/div whose class list contains a red indicator
    for tag in impact_cell.find_all(True):
        classes = " ".join(tag.get("class", [])).lower()
        title   = (tag.get("title") or "").lower()
        if "red" in classes or "high" in classes or "red" in title or "high" in title:
            return True

    return False


def scrape_events() -> list[dict]:
    """
    Fetch ForexFactory calendar and return list of HIGH impact USD events.
    Each item: { time, currency, impact, event }
    """
    resp = requests.get(FF_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # ── DEBUG: print all unique impact cell HTML snippets so we can see FF's structure ──
    table = soup.find("table", class_="calendar__table")
    if not table:
        # FF may have changed layout — dump a snippet of raw HTML for diagnosis
        snippet = resp.text[5000:8000]
        print(f"DEBUG: calendar__table not found. HTML snippet:\n{snippet}")
        raise RuntimeError("Could not find calendar table — ForexFactory layout may have changed.")

    # Print sample impact cells for debugging
    impact_cells_seen = set()
    for row in table.find_all("tr", class_=re.compile(r"calendar__row")):
        cell = row.find("td", class_="calendar__impact")
        if cell:
            cell_str = str(cell)[:200]
            if cell_str not in impact_cells_seen:
                impact_cells_seen.add(cell_str)
                print(f"DEBUG impact cell: {cell_str}")

    events       = []
    current_time = ""

    for row in table.find_all("tr", class_=re.compile(r"calendar__row")):
        if "calendar__row--day-breaker" in row.get("class", []):
            break  # moved past today into tomorrow

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

        # Impact — use broad matcher
        impact_cell = row.find("td", class_="calendar__impact")
        if not is_high_impact(impact_cell):
            continue

        # Event name
        event_cell = row.find("td", class_="calendar__event")
        if not event_cell:
            continue
        event_name = event_cell.get_text(strip=True)

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
