import sys
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START_DATE = datetime.strptime('2026-09-25', '%Y-%m-%d').date()
END_DATE = datetime.strptime('2026-10-25', '%Y-%m-%d').date()

OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'vedomosti-ru.tsv'))

def extract_date_from_url(url: str):
    """Extract YYYY-MM-DD from a Vedomosti article URL.
    Expected pattern contains /YYYY/MM/DD/ somewhere.
    Returns date object or None.
    """
    m = re.search(r'/([0-9]{4})/([0-9]{2})/([0-9]{2})/', url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        except ValueError:
            return None
    return None

def fetch_xml(url: str):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch {url}: status {status}')
        return None
    try:
        return ET.fromstring(text.encode('utf-8'))
    except ET.ParseError as e:
        print(f'XML parse error for {url}: {e}')
        return None

def parse_sitemap(root):
    """Parse a sitemap XML root.
    Returns two lists: article URLs, child sitemap URLs.
    """
    article_urls = []
    child_sitemaps = []
    # Namespace handling – strip if present
    ns = ''
    if root.tag.startswith('{'):
        ns = root.tag.split('}')[0] + '}'
    for child in root:
        if child.tag == f'{ns}sitemap':
            loc = child.find(f'{ns}loc')
            if loc is not None and loc.text:
                child_sitemaps.append(loc.text.strip())
        elif child.tag == f'{ns}url':
            loc = child.find(f'{ns}loc')
            if loc is not None and loc.text:
                article_urls.append(loc.text.strip())
    return article_urls, child_sitemaps

def collect_article_urls():
    # Start with the main sitemap index
    queue = ["https://www.vedomosti.ru/sitemap.xml"]
    seen_sitemaps = set()
    articles = set()
    while queue:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)
        root = fetch_xml(sitemap_url)
        if root is None:
            continue
        article_urls, child_sitemaps = parse_sitemap(root)
        # Add child sitemaps for further processing
        for cs in child_sitemaps:
            if cs not in seen_sitemaps:
                queue.append(cs)
        # Process article URLs
        for url in article_urls:
            date = extract_date_from_url(url)
            if date is None:
                continue
            if START_DATE <= date <= END_DATE:
                articles.add((url, date.isoformat()))
    return articles

def write_output(articles):
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    # Sort by date then url for reproducibility
    sorted_items = sorted(articles, key=lambda x: (x[1], x[0]))
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, date in sorted_items:
            f.write(f"{url}\t{date}\n")
    # Print daily counts
    from collections import Counter
    counter = Counter([d for _, d in sorted_items])
    for day in sorted(counter):
        print(f"{day}: {counter[day]} URLs")

if __name__ == '__main__':
    articles = collect_article_urls()
    write_output(articles)
    print(f"Total URLs written: {len(articles)}")
