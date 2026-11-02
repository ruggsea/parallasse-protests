#!/usr/bin/env python3
import sys, os, csv, json, datetime, re

# Add path for polite_fetch
sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12
}

def parse_date_from_text(text: str) -> datetime.date | None:
    # Look for patterns like '26 de octubre' possibly with day of week before.
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóúñ]+)", text, re.IGNORECASE)
    if not m:
        return None
    day = int(m.group(1))
    month_name = m.group(2).lower()
    month = MONTHS.get(month_name)
    if not month:
        return None
    return datetime.date(2026, month, day)

def fetch_programs_home():
    status, text, _ = fetch("https://www.13.cl/")
    if status != 200:
        return []
    # Find program slugs in hrefs like /programas/<slug>/
    return list({m.group(1) for m in re.finditer(r"/programas/([^/]+)/", text)})

def fetch_program_items(program: str):
    url = f"https://www.13.cl/export/programas/{program}/recomendados.json"
    status, text, _ = fetch(url)
    if status != 200:
        return []
    try:
        items = json.loads(text)
    except Exception:
        return []
    result = []
    for itm in items:
        title = itm.get("title", "")
        path = itm.get("path", "")
        full_url = f"https://www.13.cl{path}"
        dt = parse_date_from_text(title) or parse_date_from_text(path)
        if dt and START <= dt <= END:
            result.append((dt, full_url))
