import os
import re
import sys
import json
from urllib.parse import urljoin

# Add repository root to sys.path for importing polite_fetch
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from polite_fetch import fetch as polite_fetch

# Target dates: start, middle, end of the required range
TARGET_DATES = [
    "2026-09-25",
    "2026-10-05",
    "2026-10-25",
]

BASE_URL = "https://www.kurdistan24.net/ckb/search"
OUTPUT_TSV = os.path.abspath(os.path.join(repo_root, "data/urls_custom/kurdistan24-net.tsv"))
NOTES_JSON = os.path.abspath(os.path.join(repo_root, "out/kurdistan24-net.json.part"))

def fetch_page(date, page):
    url = f"{BASE_URL}?date={date}&page={page}"
    return polite_fetch(url, timeout=30)

def parse_html(html):
    # Extract story URLs and their date from <time datetime="YYYY-MM-DD ...">
    pattern = re.compile(r'href="(https://www\.kurdistan24\.net/ckb/story/[^\"]+)"[^>]*>.*?<time[^>]*datetime="(\d{4}-\d{2}-\d{2}) [^\"]+"', re.DOTALL)
    return pattern.findall(html)

def collect_for_date(date, min_needed=15):
    results = []
    seen = set()
    page = 1
    while len(results) < min_needed:
        html = fetch_page(date, page)
        if not html:
            break
        matches = parse_html(html)
        if not matches:
            break
        for url, dt in matches:
            if url not in seen:
                seen.add(url)
                results.append((url, dt))
        page += 1
        if page > 50:
            break
    return results

def main():
    all_entries = []
    for d in TARGET_DATES:
        entries = collect_for_date(d, min_needed=15)
        if len(entries) < 15:
            sys.stderr.write(f"Warning: only found {len(entries)} URLs for {d}\n")
        all_entries.extend(entries)

    # Deduplicate across dates
    unique = {}
    for url, dt in all_entries:
        unique[url] = dt

    # Write TSV (no header)
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, "w", encoding="utf-8") as f:
        for url, dt in unique.items():
            f.write(f"{url}\t{dt}\n")

    # Update notes JSON
    notes = {}
    if os.path.exists(NOTES_JSON):
        try:
            with open(NOTES_JSON, "r", encoding="utf-8") as jf:
                notes = json.load(jf)
        except Exception:
            notes = {}
    notes.update({
        "script": os.path.relpath(__file__, repo_root),
        "dates": TARGET_DATES,
        "total_urls": len(unique),
        "status": "completed",
    })
    os.makedirs(os.path.dirname(NOTES_JSON), exist_ok=True)
    with open(NOTES_JSON, "w", encoding="utf-8") as jf:
        json.dump(notes, jf, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
