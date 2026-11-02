#!/usr/bin/env python3
import sys, os, re, time, datetime, json
from pathlib import Path

# Ensure the polite_fetch module is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scrapers'))
try:
    from polite_fetch import fetch
except Exception as e:
    sys.stderr.write(f"Failed to import polite_fetch: {e}\n")
    sys.exit(1)

BASE_URL = "https://albaniandailynews.com"
OUTPUT_TSV = Path(__file__).resolve().parents[3] / 'data' / 'urls_custom' / 'albaniandailynews-com.tsv'

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def cdx_query(day: datetime.date):
    """Query Wayback CDX for a single day, return list of (timestamp, url)."""
    url = (
        f"http://web.archive.org/cdx/search/cdx?url={BASE_URL}/*"
        f"&from={day.isoformat()}&to={day.isoformat()}"
        f"&output=json&fl=timestamp,original&filter=statuscode:200&collapse=urlkey"
    )
    for attempt in range(3):
        status, text, _ = fetch(url)
        if status == 200 and text:
            try:
                data = json.loads(text)
                # first row is header
                return data[1:]
            except Exception:
                pass
        time.sleep(2 ** attempt)
    return []

def extract_date(html: str):
    """Extract date from <span class=\"meta_date\">...</span>. Returns date object or None."""
    m = re.search(r'<span\s+class=["\']meta_date["\']>([^<]+)</span>', html, re.IGNORECASE)
    if not m:
        return None
    txt = m.group(1).strip()
    # Expected format like "Sunday, October 25, 2026"
    try:
        return datetime.datetime.strptime(txt, "%A, %B %d, %Y").date()
    except Exception:
        # fallback: try without weekday
        try:
            txt2 = re.sub(r'^[A-Za-z]+,\s*', '', txt)
            return datetime.datetime.strptime(txt2, "%B %d, %Y").date()
        except Exception:
            return None

def main():
    seen = set()
    per_day_counts = {}
    day = START
    while day <= END:
        records = cdx_query(day)
        for ts, url in records:
            if url in seen:
                continue
            # fetch the article (use the live URL, not archive)
            status, text, _ = fetch(url)
            if status != 200 or not text:
                continue
            pub_date = extract_date(text)
            if pub_date is None:
                continue
            # accept if within one day of the target day
            if abs((pub_date - day).days) <= 1:
                seen.add(url)
                per_day_counts.setdefault(pub_date, 0)
                per_day_counts[pub_date] += 1
        day += datetime.timedelta(days=1)
    # write TSV
    OUTPUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_TSV, "w", encoding="utf-8") as f:
        for url in sorted(seen):
            # we need the stored date; reuse extract_date (fetch again) minimal overhead
            status, text, _ = fetch(url)
            pub = extract_date(text)
            if pub:
                f.write(f"{url}\t{pub.isoformat()}\n")
    # print summary
    for d in sorted(per_day_counts):
        print(f"{d}: {per_day_counts[d]} URLs")

if __name__ == "__main__":
    main()
