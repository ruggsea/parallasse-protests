"""Write data/article_meta.tsv.gz: per labelled article its date, title, text length and paywall flag, no article text.
build_report.py reads this file when data/articles/ (copyrighted text, not shipped) is absent. Needs data/articles/, so run it where the text was scraped.
Usage (repo root): python analysis/make_article_meta.py"""
import csv, gzip, json, os, sys, collections
sys.path.insert(0, 'scrapers'); sys.path.insert(0, 'analysis')
from constants import opn
from mark_paywall import is_truncated
MERGE_OUTLET = {'rai-it': 'rainews-it'}   # same as build_report.py
need = collections.defaultdict(set)
for l in opn('data/framing_A.jsonl'):
    r = json.loads(l); need[MERGE_OUTLET.get(r['outlet'], r['outlet'])].add(r['url'])
rows = []
for o, us in sorted(need.items()):
    p = 'data/articles/%s.jsonl' % o
    if not os.path.exists(p): continue
    for l in open(p):
        d = json.loads(l)
        if d['url'] in us and d.get('status', 200) == 200:
            rows.append((d['url'], (d.get('date') or d.get('listed_date') or '')[:10], (d.get('title') or '').replace('\t', ' ').replace('\n', ' '), len(d.get('text') or ''), int(bool(is_truncated(d)))))
with gzip.open('data/article_meta.tsv.gz.tmp', 'wt', newline='') as f:
    w = csv.writer(f, delimiter='\t', lineterminator='\n'); w.writerow(['url', 'date', 'title', 'textlen', 'trunc']); w.writerows(rows)
os.replace('data/article_meta.tsv.gz.tmp', 'data/article_meta.tsv.gz')
print(len(rows), 'articles with metadata')
