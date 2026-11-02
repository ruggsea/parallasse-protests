import sys, os
sys.path.insert(0, os.path.abspath('scrapers'))
from polite_fetch import fetch
status, text, _ = fetch('https://www.ex-ante.cl/news-sitemap.xml')
print('status', status)
print(text[:500])
