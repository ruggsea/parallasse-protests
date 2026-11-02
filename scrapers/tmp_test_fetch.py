import sys, json
sys.path.insert(0, './scrapers')
from polite_fetch import fetch
status, text, _ = fetch('https://midi-madagasikara.mg/')
print('status', status)
print('len', len(text) if text else 0)
