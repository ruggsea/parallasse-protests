import os
import csv
import json
import datetime
import urllib.parse
from polite_fetch import fetch

# Configuration
BASE_URL = "https://web.archive.org/cdx/search/cdx"
TARGET_PATTERN = "orf.at/stories/*"
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/urls_custom/orf-at.tsv"))
NOTE_JSON = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "grids/custom/out/orf-at.json.part"))

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + datetime.timedelta(n)

def query_wayback(date_str):
    """Query Wayback CDX for a specific date (YYYYMMDD). Returns list of (url, timestamp)."""
    params = {
        "url": TARGET_PATTERN,
        "from": date_str,
        "to": date_str,
        "output": "json",
        "fl": "original,timestamp",
        "filter": "statuscode:200",
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    response = fetch(url)
    if response.status != 200:
        raise RuntimeError(f"Wayback request failed: {response.status}")
    data = json.loads(response.text)
    # First element is header ['original','timestamp']
    return [(row[0], row[1]) for row in data[1:]]

def collect_urls(start_date, end_date, min_per_day=15):
    collected = []
    for single_date in daterange(start_date, end_date):
        date_str = single_date.strftime("%Y%m%d")
        try:
            rows = query_wayback(date_str)
        except Exception as e:
            print(f"[WARN] Could not fetch for {date_str}: {e}")
            continue
        # Deduplicate URLs for the day
        urls = list({url for url, _ in rows})
        if len(urls) < min_per_day:
            print(f"[INFO] Only found {len(urls)} URLs for {single_date.isoformat()} (need {min_per_day})")
        for url in urls:
            collected.append((url, single_date.isoformat()))
    return collected

def write_tsv(records):
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        for url, date in records:
            writer.writerow([url, date])
    print(f"Wrote {len(records)} rows to {OUTPUT_TSV}")

def update_note_json():
    try:
        with open(NOTE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["notes"] = "scraper generated URLs"
    with open(NOTE_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated note JSON at {NOTE_JSON}")

if __name__ == "__main__":
    # Define the required range
    START = datetime.date(2026, 9, 25)
    END = datetime.date(2026, 10, 25)
    records = collect_urls(START, END)
    write_tsv(records)
    update_note_json()
