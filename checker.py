import requests
import os
from datetime import datetime, timedelta, timezone

SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", "")

ET = timezone(timedelta(hours=-4))  # EDT (change to -5 in winter)

def date_range(start, end):
    d = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    dates = set()
    while d <= e:
        dates.add(d.isoformat())
        d += timedelta(days=1)
    return dates

def weekend_dates(start, end):
    d = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    dates = set()
    while d <= e:
        if d.weekday() in (4, 5):
            dates.add(d.isoformat())
        d += timedelta(days=1)
    return dates

SUMMER = date_range("2026-06-15", "2026-09-15")
BIG_PINE_BISHOP = date_range("2026-06-20", "2026-07-18")
WEEKEND_WINDOW = weekend_dates("2026-06-20", "2026-07-15")
BISHOP_DATES = {"2026-07-18", "2026-07-19"}

PERMITS = [
    {"name": "Sahale Glacier Camp", "permit_id": "4675322", "trailhead": None, "dates": SUMMER, "url": "https://www.recreation.gov/permits/4675322"},
    {"name": "Enchantments Core Zone", "permit_id": "233273", "trailhead": "Core Enchantment Zone", "dates": SUMMER, "url": "https://www.recreation.gov/permits/233273"},
    {"name": "Big Pine Lakes (JM23 North Fork)", "permit_id": "233262", "trailhead": "JM23", "dates": BIG_PINE_BISHOP, "url": "https://www.recreation.gov/permits/233262"},
    {"name": "Half Dome / Happy Isles to LYV", "permit_id": "445859", "trailhead": "Happy Isles->Little Yosemite Valley", "dates": BIG_PINE_BISHOP, "url": "https://www.recreation.gov/permits/445859"},
    {"name": "Happy Isles to LYV (weekends)", "permit_id": "445859", "trailhead": "Happy Isles->Little Yosemite Valley", "dates": WEEKEND_WINDOW, "url": "https://www.recreation.gov/permits/445859"},
    {"name": "Lyell Canyon (Donohue Pass Eligible)", "permit_id": "445859", "trailhead": "Lyell Canyon (Donohue Pass Eligible)", "dates": SUMMER, "url": "https://www.recreation.gov/permits/445859"},
    {"name": "Cottonwood Pass (weekends)", "permit_id": "233262", "trailhead": "Cottonwood Pass", "dates": WEEKEND_WINDOW, "url": "https://www.recreation.gov/permits/233262"},
    {"name": "Bishop Pass", "permit_id": "233262", "trailhead": "Bishop Pass", "dates": BISHOP_DATES, "url": "https://www.recreation.gov/permits/233262"},
]

HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.recreation.gov/", "Accept": "application/json"}

def months_in_range(dates):
    months = set()
    for d in dates:
        months.add(d[:7] + "-01")
    return sorted(months)

def fetch_permit_availability(permit_id, month_str):
    url = f"https://www.recreation.gov/api/permits/{permit_id}/divisions/availability/month"
    params = {"start_date": f"{month_str}T00:00:00.000Z", "commercial_acct": "false"}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        return None
    except:
        return None

def find_available_dates(data, target_dates, trailhead_filter):
    found = []
    if not data:
        return found
    divisions = data.get("payload", {}).get("permit_divisions", {})
    for div_id, div in divisions.items():
        div_name = div.get("name", div_id)
        if trailhead_filter and trailhead_filter.lower() not in div_name.lower():
            continue
        availability = div.get("date_availability", {})
        for date_str, info in availability.items():
            day = date_str[:10]
            if day not in target_dates:
                continue
            remaining = info.get("remaining", 0)
            status = info.get("status", "")
            if remaining > 0 or status.lower() in ("available", "open"):
                found.append((day, div_name, remaining))
    return sorted(found)

def run_checks():
    results = []
    checked_at = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    for permit in PERMITS:
        print(f"\nChecking: {permit['name']}")
        all_openings = []
        for month_str in months_in_range(permit["dates"]):
            data = fetch_permit_availability(permit["permit_id"], month_str)
            openings = find_available_dates(data, permit["dates"], permit["trailhead"])
            all_openings.extend(openings)
        if all_openings:
            print(f"  Found {len(all_openings)} opening(s)")
            results.append({"name": permit["name"], "url": permit["url"], "openings": all_openings})
        else:
            print(f"  Nothing available")
    return results, checked_at

def build_slack_message(results, checked_at):
    if not results:
        return {"text": f":camping: *Basecamp Bot* — {checked_at}\n\nNo openings found."}
    lines = [f":camping: *Basecamp Bot — Openings Found!* — {checked_at}\n"]
    for r in results:
        lines.append(f"*{r['name']}*")
        for day, division, remaining in r["openings"]:
            quota = f"{remaining} spot(s)" if remaining else "spots available"
            lines.append(f"  • {day} — {division} — {quota}")
        lines.append(f"  <{r['url']}|Book now>")
        lines.append("")
    return {"text": "\n".join(lines)}

def send_slack(message):
    if not SLACK_WEBHOOK:
        print(message["text"])
        return
    requests.post(SLACK_WEBHOOK, json=message, timeout=10)

if __name__ == "__main__":
    print(f"=== Basecamp Bot {datetime.now(ET)} ===")
    results, checked_at = run_checks()
    send_slack(build_slack_message(results, checked_at))
    print("\n=== Done ===")
