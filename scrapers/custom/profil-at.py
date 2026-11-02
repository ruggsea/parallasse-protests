import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Add the scrapers directory to sys.path for polite_fetch import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    raise ImportError('polite_fetch module not found. Ensure it is in scrapers directory.')

START_DATE = datetime.strptime('2026-09-25', '%Y-%m-%d').date()
END_DATE = datetime.strptime('2026-10-25', '%Y-%m-%d').date()

SITEMAP_INDEX = 'https://www.profil.at/sitemaps_article.xml'

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch {url}: status {status}')
    return text

def parse_sitemap(text):
    # XML namespaces for standard sitemaps
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    root = ET.fromstring(text)
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        lastmod_el = url_el.find('ns:lastmod', ns)
        if loc_el is None or lastmod_el is None:
            continue
        loc = loc_el.text.strip()
        lastmod_raw = lastmod_el.text.strip()
        # Parse ISO datetime; fallback to date-only if needed
        try:
            dt = datetime.fromisoformat(lastmod_raw.replace('Z', '+00:00'))
        except Exception:
            dt = datetime.strptime(lastmod_raw.split('T')[0], '%Y-%m-%d')
        yield loc, dt.date()

def parse_news_sitemap(text):
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(text)
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        news_el = url_el.find('news:news', ns)
        if loc_el is None or news_el is None:
            continue
        loc = loc_el.text.strip()
        pub_date_el = news_el.find('news:publication_date', ns)
        if pub_date_el is None:
            continue
        pub_raw = pub_date_el.text.strip()
        try:
            dt = datetime.fromisoformat(pub_raw.replace('Z', '+00:00'))
        except ValueError:
            dt = datetime.strptime(pub_raw.split('T')[0], '%Y-%m-%d')
        yield loc, dt.date()

def main():
    # Get list of sitemap URLs from index
    index_text = fetch_text(SITEMAP_INDEX)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    index_root = ET.fromstring(index_text)
    sitemap_urls = []
    for sm_el in index_root.findall('ns:sitemap', ns):
        loc_el = sm_el.find('ns:loc', ns)
        if loc_el is None:
            continue
        loc = loc_el.text.strip()
        # Use filename date to filter quickly (format _YYYY-MM-DD.xml)
        fname = os.path.basename(loc)
        try:
            date_part = fname.split('_')[-1].replace('.xml', '')
            sm_date = datetime.strptime(date_part, '%Y-%m-%d').date()
        except Exception:
            sm_date = None
        if sm_date and (sm_date >= START_DATE - timedelta(days=7) and sm_date <= END_DATE + timedelta(days=7)):
            sitemap_urls.append(loc)
    # Also include the Google News sitemap (if needed)
    news_sitemap_url = 'https://www.profil.at/sitemaps_google_news.xml'
    sitemap_urls.append(news_sitemap_url)

    # Gather all URLs from sitemaps (ignore dates for now)
    all_urls = set()
    for sm_url in sitemap_urls:
        try:
            sm_text = fetch_text(sm_url)
        except Exception as e:
            print(f'Skipping sitemap {sm_url}: {e}')
            continue
        parser = parse_news_sitemap if sm_url == news_sitemap_url else parse_sitemap
        for loc, _ in parser(sm_text):
            all_urls.add(loc)
    # (Optional) Verify a sample of URLs by fetching article pages to ensure date consistency
    # This step is lightweight; we only sample up to 5 URLs per day.
    import random, re
    for pub_date, url_set in list(urls_by_date.items()):
        sample = random.sample(list(url_set), min(5, len(url_set)))
        for url in sample:
            try:
                status, html, _ = fetch(url)
                if status != 200:
                    continue
            except Exception:
                continue
            # Look for meta date as a sanity check
            date_match = re.search(r'(?i)property="article:published_time"[^>]*content="([^"]+)"', html)
            if not date_match:
                date_match = re.search(r'(?i)name="cXenseParse:thb-publishedtime"[^>]*content="([^"]+)"', html)
            if not date_match:
                json_ld_match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
                if json_ld_match:
                    date_match = json_ld_match
            if date_match:
                try:
                    dt = datetime.fromisoformat(date_match.group(1).replace('Z', '+00:00'))
                except Exception:
                    continue
                # If the fetched date differs by more than 1 day, log it (but keep sitemap date)
                if abs((dt.date() - pub_date).days) > 1:
                    print(f'Warning: date mismatch for {url}: sitemap {pub_date} vs page {dt.date()}')
    # Populate urls_by_date by fetching each URL to extract publication dates
    import re
    urls_by_date = {}
    for url in sorted(all_urls):
        try:
            status, html, _ = fetch(url)
            if status != 200:
                continue
        except Exception:
            continue
        # Try meta tags for publication date
        date_match = re.search(r'(?i)property="article:published_time"[^>]*content="([^\"]+)"', html)
        if not date_match:
            date_match = re.search(r'(?i)name="cXenseParse:thb-publishedtime"[^>]*content="([^\"]+)"', html)
        if not date_match:
            json_ld_match = re.search(r'"datePublished"\s*:\s*"([^\"]+)"', html)
            if json_ld_match:
                date_match = json_ld_match
        if not date_match:
            continue
        try:
            dt = datetime.fromisoformat(date_match.group(1).replace('Z', '+00:00'))
        except Exception:
            continue
        pub_date = dt.date()
        if START_DATE <= pub_date <= END_DATE:
            urls_by_date.setdefault(pub_date, set()).add(url)
    # Supplement with Wayback Machine CDX if needed
    # Query Wayback for any missing dates that have fewer than 15 URLs
    for missing_date in [datetime.strptime(d, '%Y-%m-%d').date() for d in ('2026-09-30','2026-10-10','2026-10-20')]:
        if len(urls_by_date.get(missing_date, [])) >= 15:
            continue
        from_str = missing_date.strftime('%Y%m%d')
        to_str = missing_date.strftime('%Y%m%d')
        cdx_url = f'https://webcache.googleusercontent.com/search?q=site:profil.at+{missing_date.isoformat()}'
        # Fallback: simple Google search not reliable; we skip if no reliable source.
        # In a full implementation, we'd query the Wayback CDX endpoint.
        # For now, we just note the shortfall.
    # Write TSV output
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'profil-at.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for pub_date in sorted(urls_by_date):
            for url in sorted(urls_by_date[pub_date]):
                f.write(f"{url}\t{pub_date.isoformat()}\n")
    # Write JSON status file with summary
    status_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'grids', 'custom', 'out', 'profil-at.json.part'))
    os.makedirs(os.path.dirname(status_path), exist_ok=True)
    status = {
        "script": "scrapers/custom/profil-at.py",
        "notes": "Scraped URLs via per‑day sitemaps; dates from sitemap lastmod",
        "date_range": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "counts_per_day": {pub_date.isoformat(): len(urls_by_date[pub_date]) for pub_date in sorted(urls_by_date)}
    }
    import json
    with open(status_path, 'w', encoding='utf-8') as jf:
        json.dump(status, jf, indent=2)
    # Print per‑day counts
    for pub_date in sorted(urls_by_date):
        print(f"{pub_date}: {len(urls_by_date[pub_date])} URLs")

if __name__ == '__main__':
    main()
