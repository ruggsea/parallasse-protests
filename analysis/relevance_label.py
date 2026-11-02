"""Stage 5, step B: model labels each keyword candidate. Usage: relevance_label.py PORT MODELNAME OUT.jsonl [N_SAMPLE] [WORKERS]
Input shown to the model: outlet country, title, first 1500 chars of text. One fixed prompt, temperature 0."""
import json, sys, csv, random, urllib.request, concurrent.futures as cf, os, threading
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); from constants import opn
port, model, outp = sys.argv[1], sys.argv[2], sys.argv[3]
nsample = int(sys.argv[4]) if len(sys.argv) > 4 else 0
workers = int(sys.argv[5]) if len(sys.argv) > 5 else 8
country = {r['id']: r['country'] for r in csv.DictReader(open('data/ledger.tsv'), delimiter='\t')}
PROMPT = """You label news articles for a study of media coverage of youth and student protests (September 25 - October 25, 2026).
Outlet country: {country}
Title: {title}
Text start: {text}

Answer with one JSON object and nothing else:
{{"protest": 0 or 1, "youth": 0 or 1}}
protest = 1 if the article is mainly about a protest, demonstration, strike, school/university occupation or street clashes (anywhere in the world); 0 if it only mentions the word in passing or is about something else (sport, war, markets, a product demo).
youth = 1 if protest = 1 and the protesters are students, school pupils, young people or "Gen Z"; otherwise 0."""
rows = list(csv.DictReader(opn(os.environ.get('CAND','data/relevance_candidates.tsv')), delimiter='\t'))
if nsample: random.Random(1).shuffle(rows); rows = rows[:nsample]
done = set()
if os.path.exists(outp): done = {json.loads(l)['url'] for l in open(outp)}
arts = {}
for r in rows:
    if r['url'] not in done: arts.setdefault(r['outlet'], set()).add(r['url'])
need = {u for s in arts.values() for u in s}
text = {}
for o in arts:
    for l in open(f'data/articles/{o}.jsonl'):
        d = json.loads(l)
        if d['url'] in need: text[d['url']] = d
lock = threading.Lock(); out = open(outp, 'a')
def call(r):
    d = text.get(r['url'])
    if not d: return
    p = PROMPT.format(country=country.get(r['outlet'], '?'), title=d.get('title') or '', text=(d.get('text') or '')[:1500])
    body = {"model": model, "messages": [{"role": "user", "content": p}], "temperature": 0, "max_tokens": 800,
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions', json.dumps(body).encode(), {'Content-Type': 'application/json'})
    try: msg = json.load(urllib.request.urlopen(req, timeout=300))['choices'][0]['message']['content']
    except Exception as e: msg = 'ERR ' + str(e)[:80]
    with lock: out.write(json.dumps({'outlet': r['outlet'], 'url': r['url'], 'raw': msg}) + '\n'); out.flush()
with cf.ThreadPoolExecutor(workers) as ex: list(ex.map(call, [r for r in rows if r['url'] not in done]))
