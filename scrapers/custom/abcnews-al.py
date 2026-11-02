#!/usr/bin/env python3
import sys, os, json
from collections import defaultdict

# Ensure polite_fetch is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = "2026-09-25T00:00:00"
END = "2026-10-26T00:00:00"
PER_PAGE = 100

base_url = "https://abcnews.al/wp-json/wp/v2/posts"
collected = {}
page = 1
while True:
    url = (
        f"{base_url}?per_page={PER_PAGE}&after={START}&before={END}"
        f"&page={page}&_fields=id,date,link"
    )
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Stopping: status {status} on page {page}")
        break
    try:
        items = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"JSON decode error on page {page}: {e}")
        break
    if not items:
        break
    for it in items:
        link = it.get("link")
        date_time = it.get("date")
        if not link or not date_time:
            continue
        date = date_time.split('T')[0]
        # keep first occurrence
        if link not in collected:
            collected[link] = date
    page += 1

# Write TSV
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'abcnews-al.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    for link, date in sorted(collected.items(), key=lambda x: (x[1], x[0])):
        f.write(f"{link}\t{date}\n")

# Print per‑day counts
counts = defaultdict(int)
for d in collected.values():
    counts[d] += 1
for d in sorted(counts):
    print(f"{d}\t{counts[d]}")
