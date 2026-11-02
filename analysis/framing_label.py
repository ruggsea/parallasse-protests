"""Stage 6: one fixed prompt per kind (body, head), temperature 0, resumable and append-only by (url, kind).
Usage: framing_label.py MODEL(A|B) OUT.jsonl [URLLIST.txt] [WORKERS]
Input: articles with protest==1 and youth==1 in relevance_qwen.jsonl / relevance_qwen2.jsonl (or URLLIST).
Full article text is sent; it is cut only when prompt + MAX_TOKENS would pass SERVED_WINDOW (cut recorded in the row)."""
import json, sys, csv, re, os, glob, time, collections, urllib.request, concurrent.futures as cf, threading
sys.path.insert(0, os.path.dirname(__file__))
from constants import *
from tokenizers import Tokenizer
ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[1])
which, outp = sys.argv[1], sys.argv[2]
urllist = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != '-' else None
workers = int(sys.argv[4]) if len(sys.argv) > 4 else 6   # threads; at most PER_ENGINE run on one engine
# Engines serving the model of this run: same weights and settings, interchangeable; each row records which one answered.
POOL = {"A": {"local3-engine": 18767, "qwen38-parallasse@artemis": 18779, "qwen38-parallasse@hel": 18780}, "B": {"local2-engine": 18766}}[which]
SNAP, ROOT_NAME = {"A": ("models--Qwen--Qwen3.8-27B", "Qwen3.8-27B"), "B": ("models--openai--gpt-oss-120b", "gpt-oss-120b")}[which]
PER_ENGINE = {"A": {"local3-engine": 12}, "B": {"local2-engine": 6}}[which]   # local3 and local2 are shared with other work; the dedicated engines take 28 of their 32 seqs
sems = {n: threading.BoundedSemaphore(PER_ENGINE.get(n, 28)) for n in POOL}
alive = {}; served = {}; alive_at = [0]
def live_engines():
    if time.time() - alive_at[0] > 30:
        for n, port in POOL.items():
            try:
                r = json.load(urllib.request.urlopen('http://127.0.0.1:%d/v1/models' % port, timeout=3))['data'][0]
                alive[n] = ROOT_NAME in r.get('root', ''); served[n] = r['id']   # identity = weights path, not served name
            except Exception: alive[n] = False
        alive_at[0] = time.time()
    return [n for n in POOL if alive.get(n)]
tok = Tokenizer.from_file(glob.glob(os.environ['HF_HOME'] + '/hub/%s/snapshots/*/tokenizer.json' % SNAP)[0])
VARIANT = os.environ.get('VARIANT', '')   # '' = production prompt; 'nocountry' / 'swap' = bias test (2026-10-30)
import random, zlib
country = {r['id']: r['country'] for r in csv.DictReader(open(ROOT + '/data/ledger.tsv'), delimiter='\t')}

BODY = """You code one news article for a study of how media cover youth and student protests (articles from 2026-09-25 to 2026-10-25, any language; the article may be about a protest in another country than the outlet's). Work only from the text given. Answer with ONE JSON object and nothing else.

Outlet country: {country}
Title: {title}
Text: {text}

Fields:
- stance_protesters: "supportive" | "neutral" | "hostile". Judge the evaluative language of the article toward the protesters, not whom it quotes. neutral = reports facts without praising or blaming protesters; hostile = blames, mocks, belittles or portrays protesters as a threat or nuisance; supportive = sympathetic, endorses them.
- stance_demands: "supportive" | "neutral" | "hostile" | "not_mentioned". Same, toward what the protesters ask for.
- protest_type: "school_student" | "labour" | "climate" | "far_right" | "mixed" | "other"
- protest_country: the country where the protest takes place, in English (or "unspecified")
- region: list from ["north","centre","south","national","unspecified"], the part of that country
- share_violence_sentences: float 0-1, share of sentences about clashes, disorder, damage, injuries, policing
- share_demands_sentences: float 0-1, share of sentences about what the protesters want and why
- quoted: list of {{"role": one of police|government|protester|organiser|expert|business|other, "count": int}}, people quoted or cited directly or indirectly
- delegitimising_terms: list of words or phrases copied exactly from the article (in its own language) that label protesters as criminals, vandals, thugs, troublemakers, extremists, spoiled youth or similar. Empty list if none.

Examples (stance only): hostile "these spoiled kids skip class for a day out and call it politics; their demands are a joke and the rest of us pay for it." / neutral "The march set off at 10; police counted about a hundred, organisers two thousand. No injuries." / supportive "Thousands marched for the climate: students demand a binding plan."
Answer only the JSON object."""
HEAD = """Headline of a news article about a youth or student protest (any language): {title}
Answer with ONE JSON object: {{"headline_stance_protesters": "supportive"|"neutral"|"hostile", "headline_frame": "violence"|"demands"|"other"}}. headline_frame = what the headline foregrounds: clashes/disorder/policing, the protesters' reasons and demands, or something else. Only the JSON."""

def key(l):
    try:
        j = json.loads(l)
        return None if j['raw'].startswith('ERR') else (j['url'], j['kind'])
    except Exception: return None
done = {key(l) for l in open(outp)} if os.path.exists(outp) else set()
want = {}
if urllist: urls = set(open(urllist).read().split())
else: urls = None
for f in ['data/relevance_qwen.jsonl', 'data/relevance_qwen2.jsonl']:
    for l in opn(ROOT + '/' + f):
        o = json.loads(l); m = re.search(r'\{.*?\}', o['raw'], re.S); j = json.loads(m.group(0))
        if j['protest'] == 1 and j['youth'] == 1 and (urls is None or o['url'] in urls): want[o['url']] = o['outlet']
def suffixes(outlet):
    """Trailing ' - Name' / ' | Name' segments (<=40 chars) found on 20+ titles of the outlet: the outlet name appended to titles."""
    c = collections.Counter()
    for l in open(ROOT + '/data/articles/%s.jsonl' % outlet):
        t = json.loads(l).get('title') or ''
        m = re.search(r'\s[-|–—]\s([^-|–—]{2,40})$', t)
        if m: c[m.group(1).strip()] += 1
    return {k for k, v in c.items() if v >= 20}
SUMMARY_LINES = ('Resumen IA', 'Gerando resumo', 'Key Points', 'Resumo IA', 'AI summary')
def norm(t): return re.sub(r'\W+', ' ', t).lower().strip()
def clean(d, outlet):
    """Same rules for every outlet: strip the outlet-name suffix from the title, drop a first body line that repeats the title (exact or one contains the other), drop machine-summary header lines."""
    d = dict(d); t = d['title'].strip()
    for sfx in SFX[outlet]:
        for sep in (' - ', ' | ', ' – ', ' — '):
            if t.endswith(sep + sfx): t = t[:-len(sep + sfx)].strip()
    d['title'] = t
    lines = [x for x in (d.get('text') or '').strip().split('\n') if x.strip() not in SUMMARY_LINES]
    while lines and (norm(lines[0]) == norm(t) or (len(norm(lines[0])) > 15 and (norm(lines[0]) in norm(t) or norm(t) in norm(lines[0])))): lines = lines[1:]
    d['text'] = '\n'.join(lines).strip()
    return d
rows = {}
SFX = {o: suffixes(o) for o in set(want.values())}
for o in set(want.values()):
    for l in open(ROOT + '/data/articles/%s.jsonl' % o):
        d = json.loads(l)
        day = (d.get('date') or d.get('listed_date') or '')[:10]
        if d['url'] in want and d.get('status') == 200 and d.get('title') and WINDOW[0] <= day <= WINDOW[1]: rows[d['url']] = clean(d, o)
head600 = collections.Counter((want[u], d['text'][:DUP_HEAD_CHARS]) for u, d in rows.items() if len(d['text']) >= MIN_BODY_CHARS)
dup_body = {u for u, d in rows.items() if len(d['text']) >= MIN_BODY_CHARS and head600[(want[u], d['text'][:DUP_HEAD_CHARS])] > 1}   # same first 600 chars as another article of the same outlet (stored live-blog text, cookie walls): no body call
jobs = [(want[u], u, k) for u in sorted(rows) for k in (('body',) if VARIANT else ('head', 'body')) if (u, k) not in done and (k == 'head' or (len(rows[u]['text']) >= MIN_BODY_CHARS and u not in dup_body))]
lock = threading.Lock(); out = open(outp, 'a'); ctr = [0]

def shown_country(outlet, url):
    c = country.get(outlet, '?')
    if VARIANT != 'swap': return c
    others = sorted({v for v in country.values() if v and v != 'Italy'})
    return random.Random(zlib.crc32(url.encode())).choice(others) if c == 'Italy' else 'Italy'
def build(d, kind, outlet):
    """The exact user message sent to the model; also used by the audit. Returns (prompt, n_tokens, cut)."""
    if kind == 'head':
        p = HEAD.format(title=d.get('title') or ''); return p, len(tok.encode(p).ids), False
    text = d['text']; cut = False
    p = (BODY.replace('Outlet country: {country}\n', '') if VARIANT == 'nocountry' else BODY).format(country=shown_country(outlet, d['url']), title=d.get('title') or '', text=text)
    n = len(tok.encode(p).ids); budget = SERVED_WINDOW - MAX_TOKENS[which] - 300
    while n > budget:
        text = text[:int(len(text) * budget / n * 0.97)]; cut = True
        p = (BODY.replace('Outlet country: {country}\n', '') if VARIANT == 'nocountry' else BODY).format(country=shown_country(outlet, d['url']), title=d.get('title') or '', text=text); n = len(tok.encode(p).ids)
    return p, n, cut

def call(outlet, u, kind):
    d = rows[u]; p, n, cut = build(d, kind, outlet)
    while True:
        eng = next((n for n in live_engines() if sems[n].acquire(blocking=False)), None)
        if eng: break
        time.sleep(0.5)
    body = {"model": served[eng], "messages": [{"role": "user", "content": p}], "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS[which]}
    if which == "A": body["chat_template_kwargs"] = {"enable_thinking": False}
    else: body["reasoning_effort"] = "low"
    req = urllib.request.Request('http://127.0.0.1:%s/v1/chat/completions' % POOL[eng], json.dumps(body).encode(), {'Content-Type': 'application/json'})
    try: msg = json.load(urllib.request.urlopen(req, timeout=900))['choices'][0]['message']['content']
    except Exception as e: msg = 'ERR ' + str(e)[:100]
    finally: sems[eng].release()
    with lock:
        out.write(json.dumps({'outlet': outlet, 'url': u, 'kind': kind, 'model': which, 'engine': eng, 'prompt_tokens': n, 'cut': cut, 'raw': msg}, ensure_ascii=False) + '\n'); out.flush()
        ctr[0] += 1
        if ctr[0] % 100 == 0: print('done', ctr[0], flush=True)
if __name__ == '__main__':
    print(len(rows), 'articles,', len(jobs), 'calls to make', flush=True)
    with cf.ThreadPoolExecutor(workers) as ex: list(ex.map(lambda t: call(*t), jobs))
    print('FINISHED', ctr[0], 'of', len(jobs))
