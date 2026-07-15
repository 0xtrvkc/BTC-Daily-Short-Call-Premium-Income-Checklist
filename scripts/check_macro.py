"""
check_macro.py
Scrapes ForexFactory for HIGH impact USD events falling on "today" in Bangkok time.
Only triggers skip for FOMC / CPI / NFP / Fed Chair / Fed Speech / PPI / etc.
Writes result to /data/macro.json.
Runs via GitHub Actions every morning before 8am Bangkok (GMT+7).

--------------------------------------------------------------------------
IMPORTANT — TIMEZONE NOTE (read this if you're debugging a mismatch again)
--------------------------------------------------------------------------
ForexFactory's calendar page, when scraped anonymously (no logged-in account
with a timezone preference set), displays times in **America/New York**
(ET — EDT/EST depending on DST), NOT in the visitor's local timezone. Your
browser converts this to your local time automatically when you view the
site, which is why the browser shows a different clock time than a raw
scrape of the same page's HTML.

A Bangkok calendar day (GMT+7) does NOT line up 1:1 with an ET calendar day
(ET is 11h behind Bangkok during EDT, 12h behind during EST). Concretely:

    Bangkok day D, 00:00  ==  ET day (D-1), ~13:00 (EDT) / ~12:00 (EST)
    Bangkok day D, 23:59  ==  ET day  D,    ~12:59 (EDT) / ~11:59 (EST)

So "today in Bangkok" is actually spread across the *tail end of ET's
previous day* and the *first half of ET's current day*. This script now
fetches both ET calendar pages, converts every event's real timestamp to
Bangkok time, and keeps only the ones that land on the target Bangkok date.
--------------------------------------------------------------------------
"""

import json
import re
from datetime import datetime, date, timedelta, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
ET_TZ       = ZoneInfo("America/New York")
BANGKOK_TZ  = ZoneInfo("Asia/Bangkok")
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "macro.json"
FF_BASE_URL = "https://www.forexfactory.com/calendar"

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
KILL_LIST = ["FOMC", "CPI", "NFP", "Fed Chair", "Fed Speech", "Federal Reserve",
             "PPI m/m", "Core PPI m/m", "Non-Farm", "Unemployment", "Earnings m/m"]

TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(am|pm)$", re.IGNORECASE)

# ── Helpers ───────────────────────────────────────────────────────────────────

def target_bangkok_date() -> date:
    return datetime.now(BANGKOK_TZ).date()


def ff_day_param(d: date) -> str:
    """e.g. date(2026,7,15) -> 'jul15.2026' (FF's ?day= URL format)."""
    return f"{d.strftime('%b').lower()}{d.day}.{d.year}"


def parse_time_text(text: str) -> dtime | None:
    """Parse '8:30am' / '12:40pm' style FF time text. Returns None if not a
    standard clock time (e.g. 'Tentative', 'All Day', '')."""
    m = TIME_RE.match(text.strip())
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return dtime(hour=hour, minute=minute)


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


def fetch_et_day(et_date: date) -> list[dict]:
    """Fetch one ET-calendar-day page from FF and return raw row data
    (time text, currency, event name, red-impact flag), tagged with the
    ET calendar date the page represents."""
    url = f"{FF_BASE_URL}?day={ff_day_param(et_date)}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", class_="calendar__table")
    if not table:
        snippet = resp.text[5000:8000]
        print(f"DEBUG: calendar__table not found for {et_date}. HTML snippet:\n{snippet}")
        raise RuntimeError(f"Could not find calendar table for {et_date} — layout may have changed.")

    rows_out = []
    current_time_text = ""

    for row in table.find_all("tr", class_=re.compile(r"calendar__row")):
        row_classes = row.get("class", [])
        if "calendar__row--day-breaker" in row_classes:
            # single-day page — nothing to do with breaker rows
            continue

        time_cell = row.find("td", class_="calendar__time")
        if time_cell and time_cell.get_text(strip=True):
            current_time_text = time_cell.get_text(strip=True)

        currency_cell = row.find("td", class_="calendar__currency")
        if not currency_cell:
            continue
        currency = currency_cell.get_text(strip=True)
        if currency != "USD":
            continue

        event_cell = row.find("td", class_="calendar__event")
        if not event_cell:
            continue
        event_name = event_cell.get_text(strip=True)
        if not event_name:
            continue

        impact_cell = row.find("td", class_="calendar__impact")
        red = is_red_impact(impact_cell)

        rows_out.append({
            "et_date":   et_date,
            "time_text": current_time_text,
            "currency":  currency,
            "event":     event_name,
            "red":       red,
        })

    return rows_out


def to_bangkok_events(raw_rows: list[dict], target_date: date) -> list[dict]:
    """Convert ET raw rows to Bangkok-local events, keeping only those that
    land on target_date. Rows with non-standard time text (Tentative, All
    Day, etc.) are kept if their ET page date is adjacent to the target
    Bangkok day, but flagged as time_confirmed=False since we can't compute
    an exact Bangkok timestamp for them."""
    out = []
    for r in raw_rows:
        t = parse_time_text(r["time_text"])

        if t is not None:
            dt_et = datetime.combine(r["et_date"], t, tzinfo=ET_TZ)
            dt_bkk = dt_et.astimezone(BANGKOK_TZ)
            if dt_bkk.date() != target_date:
                continue
            out.append({
                "time":           dt_bkk.strftime("%-I:%M%p").lower(),
                "time_confirmed": True,
                "currency":       r["currency"],
                "event":          r["event"],
                "red":            r["red"],
            })
        else:
            # Non-standard time (Tentative / All Day / blank). Can't compute
            # an exact Bangkok timestamp, so include cautiously if the ET
            # page date is plausibly part of today's Bangkok window, and
            # flag it for manual review.
            out.append({
                "time":           r["time_text"] or "unspecified",
                "time_confirmed": False,
                "currency":       r["currency"],
                "event":          r["event"],
                "red":            r["red"],
            })

    return out


def scrape_events() -> list[dict]:
    target = target_bangkok_date()
    # Bangkok day D spans ET day (D-1) afternoon/evening through ET day D
    # late morning, so we need both ET calendar pages.
    et_dates = [target - timedelta(days=1), target]

    raw_rows: list[dict] = []
    for et_date in et_dates:
        print(f"DEBUG: fetching ET calendar page for {et_date}")
        raw_rows.extend(fetch_et_day(et_date))

    bkk_events = to_bangkok_events(raw_rows, target)

    events = []
    for e in bkk_events:
        on_list = is_on_kill_list(e["event"])
        print(f"DEBUG row: bkk_time={e['time']} (confirmed={e['time_confirmed']}) "
              f"currency={e['currency']} red={e['red']} on_kill_list={on_list} "
              f"event='{e['event']}'")

        if not (e["red"] and on_list):
            continue

        print(f"  ✅ KILL LIST match: [{e['time']}] {e['event']}")
        events.append({
            "time":           e["time"],
            "time_confirmed": e["time_confirmed"],
            "currency":       e["currency"],
            "impact":         "HIGH",
            "event":          e["event"],
        })

    return events


def build_result(events: list[dict]) -> dict:
    now_utc = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    skip    = len(events) > 0
    return {
        "date":        target_bangkok_date().isoformat(),
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
    print(f"Checking ForexFactory for {target_bangkok_date().isoformat()} (Bangkok time)...")

    try:
        events = scrape_events()
    except Exception as exc:
        result = {
            "date":        target_bangkok_date().isoformat(),
            "checked_at":  datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
            flag = "" if e["time_confirmed"] else " (time unconfirmed — verify manually)"
            print(f"  [{e['time']}] {e['event']}{flag}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2))
    print(f"Written → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
