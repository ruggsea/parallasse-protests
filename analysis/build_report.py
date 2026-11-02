"""Rebuilds the whole report from the labels that exist now. Re-run when data/framing_A.jsonl / framing_B.jsonl grow.
Usage: python analysis/build_report.py            (from the repo root, venv active)
Writes report/csv/*.csv, report/charts/*.{png,svg}, report/index.html, report/parallasse_protests_report.pdf, report/charts.zip.
Every number in the HTML is computed here from the data files; the Italian prose is chosen by templates from the sign and size of the intervals."""
import json, re, csv, os, sys, math, glob, base64, zipfile, collections, datetime as dt, zlib, html
import warnings; warnings.filterwarnings('ignore', category=RuntimeWarning)
import numpy as np, pandas as pd
from sklearn.metrics import cohen_kappa_score
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + '/analysis'); sys.path.insert(0, ROOT + '/scrapers')
from constants import *
from mark_paywall import is_truncated
R = ROOT + '/report'
for d in ('csv', 'charts'): os.makedirs('%s/%s' % (R, d), exist_ok=True)
BOOT, SEED = 1000, 1
RED, SAL, BLK, DARK, BG, GRID = '#C1443F', '#DB9D87', '#000000', '#323232', '#EEE7D7', '#B8AEB0'
MINN = 30   # smallest article count for a country to be shown

# ---------- helpers ----------
def atomic(path, data, mode='w'):
    tmp = path + '.tmp'
    with open(tmp, mode) as f: f.write(data)
    os.replace(tmp, path)
def write_csv(name, df):
    tmp = '%s/csv/%s.tmp' % (R, name); df.to_csv(tmp, index=False); os.replace(tmp, '%s/csv/%s.csv' % (R, name))
def it(x, d=0):
    if x is None or (isinstance(x, float) and math.isnan(x)): return 'n.d.'
    s = '{:,.{d}f}'.format(x, d=d); return s.replace(',', '§').replace('.', ',').replace('§', '.')
def pct(x, d=0): return 'n.d.' if x is None or x != x else it(100 * x, d) + '%'
def pp(x, d=1): return 'n.d.' if x is None or x != x else ('+' if x > 0 else '') + it(100 * x, d).replace('-', '−')
def esc(s): return html.escape(str(s))
def norm_country(c):
    c = re.sub(r'[^a-z ]', '', (c or '').lower()).strip()
    return {'usa': 'united states', 'us': 'united states', 'united states of america': 'united states', 'uk': 'united kingdom', 'britain': 'united kingdom',
            'great britain': 'united kingdom', 'england': 'united kingdom', 'korea': 'south korea', 'republic of korea': 'south korea', 'bosnia': 'bosnia and herzegovina',
            'czechia': 'czech republic', 'russian federation': 'russia', 'turkiye': 'turkey', 'palestinian territories': 'palestine', 'state of palestine': 'palestine'}.get(c, c)
IT_NAMES = {'Italy': 'Italia', 'France': 'Francia', 'United States': 'Stati Uniti', 'South Korea': 'Corea del Sud', 'Peru': 'Perù', 'Chile': 'Cile', 'Canada': 'Canada', 'Australia': 'Australia',
    'Russia': 'Russia', 'Romania': 'Romania', 'Nigeria': 'Nigeria', 'Netherlands': 'Paesi Bassi', 'Indonesia': 'Indonesia', 'India': 'India', 'Germany': 'Germania', 'Vietnam': 'Vietnam',
    'Turkey': 'Turchia', 'Thailand': 'Thailandia', 'Serbia': 'Serbia', 'Brazil': 'Brasile', 'Belgium': 'Belgio', 'Austria': 'Austria', 'Argentina': 'Argentina', 'Sri Lanka': 'Sri Lanka',
    'Spain': 'Spagna', 'Portugal': 'Portogallo', 'Mexico': 'Messico', 'Ireland': 'Irlanda', 'Iran': 'Iran', 'Colombia': 'Colombia', 'Bangladesh': 'Bangladesh', 'Uganda': 'Uganda',
    'Greece': 'Grecia', 'Bulgaria': 'Bulgaria', 'Albania': 'Albania', 'Venezuela': 'Venezuela', 'United Kingdom': 'Regno Unito', 'Tunisia': 'Tunisia', 'Philippines': 'Filippine',
    'Nepal': 'Nepal', 'Ecuador': 'Ecuador', 'Bosnia And Herzegovina': 'Bosnia-Erzegovina', 'Taiwan': 'Taiwan', 'North Macedonia': 'Macedonia del Nord', 'South Africa': 'Sudafrica',
    'Morocco': 'Marocco', 'Mongolia': 'Mongolia', 'Kenya': 'Kenya', 'Iraq': 'Iraq', 'Palestine': 'Palestina', 'Madagascar': 'Madagascar'}
def itn(c): return IT_NAMES.get(c, c)
def rows_of(path):
    return [json.loads(l) for l in opn(path)] if os.path.exists(path) or os.path.exists(path + '.gz') else []

# ---------- load labels ----------
ENUM = {'stance_protesters': {'supportive', 'neutral', 'hostile'}, 'stance_demands': {'supportive', 'neutral', 'hostile', 'not_mentioned'},
        'protest_type': {'school_student', 'labour', 'climate', 'far_right', 'mixed', 'other'}, 'headline_stance_protesters': {'supportive', 'neutral', 'hostile'},
        'headline_frame': {'violence', 'demands', 'other'}}
def parse_raw(raw):
    """-> (status, dict). status: ok | error | unparseable."""
    if raw.startswith('ERR'): return 'error', None
    m = re.search(r'\{.*\}', raw, re.S)
    if not m: return 'unparseable', None
    try: j = json.loads(m.group(0))
    except Exception: return 'unparseable', None
    return ('ok', j) if isinstance(j, dict) else ('unparseable', None)
def load_labels(path):
    rows = rows_of(path); stats = collections.Counter(); engines = collections.Counter(); invalid = collections.Counter(); best = {}
    for r in rows:
        st, j = parse_raw(r.get('raw') or ''); k = r['kind']
        stats[(k, 'rows')] += 1; stats[(k, st)] += 1; stats[(k, 'cut')] += bool(r.get('cut')); engines[r.get('engine')] += 1
        stats[(k, 'max_tokens')] = max(stats[(k, 'max_tokens')], r.get('prompt_tokens') or 0)
        if st == 'ok':
            for f, allowed in ENUM.items():
                if f in j and str(j[f]).strip().lower() not in allowed: invalid[f] += 1
            best[(r['url'], k)] = (r, j)
    return rows, stats, engines, invalid, best
rowsA, statsA, engA, invA, labA = load_labels(ROOT + '/data/framing_A.jsonl')
rowsB, statsB, engB, invB, labB = load_labels(ROOT + '/data/framing_B.jsonl')
def cat(j, f):
    v = str(j.get(f, '')).strip().lower() if j else ''
    return v if v in ENUM[f] else None
def num01(j, f):
    try: v = float(j[f])
    except Exception: return np.nan
    return min(max(v, 0.0), 1.0) if v == v else np.nan

# ---------- article metadata, groups, leaning ----------
ledger = {r['id']: r for r in csv.DictReader(open(ROOT + '/data/ledger.tsv'), delimiter='\t')}
urls_A = sorted({u for (u, k) in labA}); url_outlet = {}
MERGE_OUTLET = {'rai-it': 'rainews-it'}  # same feed: all 1,098 URLs identical (rainews.it); counted once
for r in rowsA: url_outlet[r['url']] = MERGE_OUTLET.get(r['outlet'], r['outlet'])
need = collections.defaultdict(set)
for u in urls_A: need[url_outlet[u]].add(u)
meta = {}
META_FILE = ROOT + '/data/article_meta.tsv.gz'
if not glob.glob(ROOT + '/data/articles/*.jsonl') and os.path.exists(META_FILE):   # article text is not shipped: use the metadata table (analysis/make_article_meta.py)
    for r in csv.DictReader(opn(META_FILE), delimiter='\t'):
        if r['url'] in url_outlet: meta[r['url']] = dict(date=r['date'], title=r['title'], textlen=int(r['textlen']), trunc=bool(int(r['trunc'])))
    need = {}
for o, us in need.items():
    p = '%s/data/articles/%s.jsonl' % (ROOT, o)
    if not os.path.exists(p): continue
    for l in open(p):
        d = json.loads(l)
        if d['url'] in us and d.get('status', 200) == 200:
            meta[d['url']] = dict(date=(d.get('date') or d.get('listed_date') or '')[:10], title=d.get('title') or '', textlen=len(d.get('text') or ''), trunc=bool(is_truncated(d)))
def dom_norm(d): return re.sub(r'^www\.', '', (d or '').strip().lower()).replace('.', '-')
def load_leaning():
    lean = {}; src = [(ROOT + '/data/leaning_italy.tsv', 'Italy')] + [(f, os.path.basename(f)[:-4].replace('_', ' ').title()) for f in sorted(glob.glob(ROOT + '/data/leaning/*.tsv'))]
    for f, c in src:
        for r in csv.DictReader(open(f), delimiter='\t'):
            if r.get('leaning') in (None, '', 'leaning') or not r.get('domain'): continue
            lean[dom_norm(r['domain'])] = (r.get('leaning_authors') or r['leaning']).strip().lower()   # Italy: the classification (Luca Bagnariol, 2026-10-30) overrides the sourced value; both stay in data/leaning_italy.tsv
    return lean
lean_by_domain = load_leaning()
def leaning_of(o):
    for key in (o, dom_norm(ledger.get(o, {}).get('domain'))):
        if key in lean_by_domain: return lean_by_domain[key]
    return 'unknown'
outlets_A = sorted(set(url_outlet.values())); unmatched = [o for o in outlets_A if leaning_of(o) == 'unknown']

recs = []
for u in urls_A:
    o = url_outlet[u]; m = meta.get(u); country = ledger.get(o, {}).get('country', '?')
    if o in os.environ.get('TEST_ITALY', '').split(','): country = 'Italy'   # test hook only: exercises the Italy paths on partial data
    hr, hj = labA.get((u, 'head'), (None, None)); br, bj = labA.get((u, 'body'), (None, None))
    d = dict(url=u, outlet=o, country=country, group='Italy' if country == 'Italy' else 'Others', leaning=leaning_of(o), has_meta=m is not None,
             title=(m or {}).get('title', ''), date=(m or {}).get('date', ''), trunc=(m or {}).get('trunc', False), textlen=(m or {}).get('textlen', 0))
    d['live'] = d['textlen'] >= LIVE_BLOG_CHARS
    d['has_head'] = hj is not None; d['has_body'] = bj is not None
    d['body_ok'] = bj is not None and m is not None and not d['trunc'] and not d['live']
    d['pc'] = norm_country(bj.get('protest_country')) if bj else None
    d['domestic'] = (d['pc'] == norm_country(country)) if bj else None
    ok = d['body_ok']
    st = cat(bj, 'stance_protesters') if ok else None
    d['hostile'] = (st == 'hostile') * 1.0 if st else np.nan
    d['supportive'] = (st == 'supportive') * 1.0 if st else np.nan
    sd = cat(bj, 'stance_demands') if ok else None
    d['hostile_dem'] = (sd == 'hostile') * 1.0 if sd in ('supportive', 'neutral', 'hostile') else np.nan
    v, e = (num01(bj, 'share_violence_sentences'), num01(bj, 'share_demands_sentences')) if ok else (np.nan, np.nan)
    d['viol'], d['dem'] = v, e
    both = v == v and e == e
    d['viol_r'], d['dem_r'] = (v, e) if both else (np.nan, np.nan)
    q = collections.Counter()
    if ok and isinstance(bj.get('quoted'), list):
        for x in bj['quoted']:
            try:
                if isinstance(x, dict) and int(x.get('count', 1)) > 0: q[str(x.get('role', '')).lower()] += int(x.get('count', 1))
            except Exception: pass
    d['q_gov'] = float(q['police'] + q['government'] > 0) if ok and isinstance(bj.get('quoted'), list) else np.nan
    d['q_prot'] = float(q['protester'] + q['organiser'] > 0) if ok and isinstance(bj.get('quoted'), list) else np.nan
    terms = [str(t).lower().strip(' "\'.,;:!?«»“”') for t in (bj.get('delegitimising_terms') or [])] if ok and isinstance(bj.get('delegitimising_terms'), list) else None
    d['terms'] = sorted({t for t in (terms or []) if t}); d['deleg'] = float(len(d['terms']) > 0) if terms is not None else np.nan
    hs = cat(hj, 'headline_stance_protesters'); hf = cat(hj, 'headline_frame')
    d['head_viol'] = (hf == 'violence') * 1.0 if hf else np.nan
    d['head_host'] = (hs == 'hostile') * 1.0 if hs else np.nan
    d['gap'] = d['head_host'] - d['hostile'] if d['head_host'] == d['head_host'] and d['hostile'] == d['hostile'] else np.nan
    recs.append(d)
df = pd.DataFrame(recs)
if df.empty: sys.exit('no labels in data/framing_A.jsonl yet')
df['week'] = df['date'].map(lambda s: (dt.date.fromisoformat(s) - dt.timedelta(days=dt.date.fromisoformat(s).weekday())).isoformat() if re.match(r'\d{4}-\d\d-\d\d$', s) else None)

METRICS = [  # key, label_it, num column, den column (None = rows where num exists), is_share
    ('hostile', 'Articoli ostili verso i manifestanti', 'hostile', None, True),
    ('supportive', 'Articoli favorevoli ai manifestanti', 'supportive', None, True),
    ('hostile_dem', 'Articoli ostili verso le richieste (dove citate)', 'hostile_dem', None, True),
    ('viol', 'Quota di frasi sulla violenza (media)', 'viol', None, True),
    ('dem', 'Quota di frasi sulle richieste (media)', 'dem', None, True),
    ('ratio', 'Rapporto frasi violenza / frasi richieste', 'viol_r', 'dem_r', False),
    ('q_gov', 'Articoli che citano polizia o governo', 'q_gov', None, True),
    ('q_prot', 'Articoli che citano manifestanti o organizzatori', 'q_prot', None, True),
    ('deleg', 'Articoli con almeno un termine delegittimante', 'deleg', None, True),
    ('head_viol', 'Titoli con cornice di violenza', 'head_viol', None, True),
    ('head_host', 'Titoli ostili verso i manifestanti', 'head_host', None, True),
    ('gap', 'Titolo meno testo: differenza di ostilità (punti)', 'gap', None, False),
]
MK = [m[0] for m in METRICS]; MLABEL = {m[0]: m[1] for m in METRICS}

def mats(d):
    """per-outlet numerators and denominators, shape (outlets, metrics)"""
    g = d.groupby('outlet'); N = []; D = []
    for k, _, nc, dc, _s in METRICS:
        if dc is None: N.append(g[nc].sum(min_count=1).fillna(0)); D.append(g[nc].count())
        else: N.append(g[nc].sum(min_count=1).fillna(0)); D.append(g[dc].sum(min_count=1).fillna(0))
    return np.array(N).T, np.array(D).T.astype(float), len(g)
def boot(d, label):
    """-> est[M], reps[B,M], n[M], k outlets, articles"""
    if len(d) == 0: return None
    Nm, Dm, k = mats(d); rng = np.random.default_rng([SEED, zlib.crc32(label.encode())])
    with np.errstate(all='ignore'):
        est = Nm.sum(0) / Dm.sum(0)
        idx = rng.integers(0, k, (BOOT, k)); reps = Nm[idx].sum(1) / Dm[idx].sum(1)
    n = Dm.sum(0); n_art = np.array([d[nc].notna().sum() if dc is None else (d[nc].notna() & d[dc].notna()).sum() for _, _, nc, dc, _s in METRICS])
    return dict(est=est, reps=reps, n=n_art, k=k, articles=len(d))
def ci(b, i):
    if b is None or b['k'] < 2: return (np.nan, np.nan)
    r = b['reps'][:, i]; r = r[~np.isnan(r)]
    return (np.percentile(r, 2.5), np.percentile(r, 97.5)) if len(r) > 100 else (np.nan, np.nan)
def table(groups, view):
    out = []
    for gname, d in groups:
        b = boot(d, view + gname)
        if b is None: continue
        for i, m in enumerate(MK):
            lo, hi = ci(b, i); out.append(dict(view=view, group=gname, metric=m, label=MLABEL[m], est=b['est'][i], lo=lo, hi=hi, n=int(b['n'][i]), n_articles=b['articles'], n_outlets=b['k']))
    return pd.DataFrame(out, columns=['view', 'group', 'metric', 'label', 'est', 'lo', 'hi', 'n', 'n_articles', 'n_outlets'])
VIEWS = {'all': df, 'domestic': df[df['domestic'] == True]}
def diff_table(view, dd, ga='Italy', gb='Others'):
    A, B = dd[dd.group == ga], dd[dd.group == gb]; ba, bb = boot(A, view + ga), boot(B, view + gb); out = []
    if ba is None and bb is None: return pd.DataFrame(columns=['view', 'metric', 'label', 'italy', 'others', 'diff', 'lo', 'hi', 'excludes_zero', 'n_italy', 'n_others'])
    nanb = lambda b: dict(est=np.full(len(MK), np.nan), reps=np.full((BOOT, len(MK)), np.nan), n=np.zeros(len(MK), int), k=0)
    ba = ba or nanb(0); bb = bb or nanb(0)
    for i, m in enumerate(MK):
        df_ = ba['reps'][:, i] - bb['reps'][:, i]; df_ = df_[~np.isnan(df_)]; est = ba['est'][i] - bb['est'][i]
        lo, hi = (np.percentile(df_, 2.5), np.percentile(df_, 97.5)) if len(df_) > 100 and ba['k'] > 1 and bb['k'] > 1 else (np.nan, np.nan)
        out.append(dict(view=view, metric=m, label=MLABEL[m], italy=ba['est'][i], others=bb['est'][i], diff=est, lo=lo, hi=hi, excludes_zero=bool(lo > 0 or hi < 0) if lo == lo else False, n_italy=int(ba['n'][i]), n_others=int(bb['n'][i])))
    return pd.DataFrame(out)

group_tabs, diffs = [], []
for view, dd in VIEWS.items():
    groups = [('Italy', dd[dd.group == 'Italy']), ('Others', dd[dd.group == 'Others'])]
    cs = dd.groupby('country')['hostile'].count(); groups += [(c, dd[dd.country == c]) for c in cs[cs >= MINN].index if c != 'Italy']   # counted on articles with a text label, the same n the charts print
    groups.append(('Small', dd[dd.country.isin(cs[cs < 50].index) & (dd.country != 'Italy')]))
    group_tabs.append(table(groups, view)); diffs.append(diff_table(view, dd))
GT = pd.concat(group_tabs, ignore_index=True); DT = pd.concat(diffs, ignore_index=True)
write_csv('metrics_by_group', GT); write_csv('italy_vs_others_difference', DT)
lean_tabs = []
for view, dd in VIEWS.items():
    gl = []
    for g in ('Italy', 'Others'):
        for lv, x in dd[dd.group == g].groupby('leaning'): gl.append((g + '|' + lv, x))
    lean_tabs.append(table(gl, view))
LT = pd.concat(lean_tabs, ignore_index=True)
if len(LT): LT[['side', 'leaning']] = LT['group'].str.split('|', n=1, expand=True)
write_csv('metrics_by_leaning', LT)
write_csv('leaning_italy', pd.read_csv(ROOT + '/data/leaning_italy.tsv', sep='\t')[['outlet', 'domain', 'leaning', 'leaning_authors', 'leaning_authors_source', 'url1']].rename(columns={'leaning': 'leaning_sourced'}))
wk = []
for g in ('Italy', 'Others'):
    for w, x in df[df.group == g].groupby('week'): wk.append((g + '|' + w, x))
WT = table(wk, 'all')
if len(WT): WT[['side', 'week']] = WT['group'].str.split('|', n=1, expand=True)
write_csv('weekly_series', WT)

# ---------- log-odds (Monroe et al. 2008, informative Dirichlet prior = counts over all articles) ----------
def log_odds(c1, c2, prior, minc=3):
    n1, n2, a0 = sum(c1.values()), sum(c2.values()), sum(prior.values()); out = []
    for w in sorted(set(c1) | set(c2)):
        y1, y2, a = c1.get(w, 0), c2.get(w, 0), prior.get(w, 0)
        if y1 + y2 < minc or a <= 0: continue
        d = math.log((y1 + a) / (n1 + a0 - y1 - a)) - math.log((y2 + a) / (n2 + a0 - y2 - a))
        z = d / math.sqrt(1 / (y1 + a) + 1 / (y2 + a)); out.append(dict(term=w, count_1=y1, count_2=y2, log_odds=d, z=z))
    return pd.DataFrame(out, columns=['term', 'count_1', 'count_2', 'log_odds', 'z']).sort_values(['z', 'term'], ascending=[False, True], kind='mergesort')
def termcount(rows):
    c = collections.Counter()
    for t in rows: c.update(set(t))
    return c
elig = df[df.body_ok & df.deleg.notna()]
cI, cO = termcount(elig[elig.group == 'Italy'].terms), termcount(elig[elig.group == 'Others'].terms); cAll = cI + cO
LOD = log_odds(cI, cO, cAll); LOD['side'] = np.where(LOD.z > 0, 'Italy', 'Others'); LOD = LOD.rename(columns={'count_1': 'articles_italy', 'count_2': 'articles_others'})
write_csv('logodds_delegitimising_terms', LOD)
IT_STOP = set('il lo la le gli i un una uno di del dello della dei degli delle da dal dalla dai dalle in nel nella nei nelle con su sul sulla per tra fra a al alla ai alle e ed o ma che chi non si più come anche è sono era essere ha hanno dopo prima sotto sopra contro fino ne ci lui lei loro questo questa questi queste quel quella suo sua suoi sue nuovo nuova dalle'.split())
ITALIAN_MARK = set('il lo la le gli di del della dei delle che per con un una nel nella sono è non si'.split())
def title_tokens(t): return [w for w in re.findall(r"[^\W\d_]{3,}", t.lower()) if w not in IT_STOP]
it_df = df[(df.group == 'Italy') & df.has_head & (df.title != '')].copy()
it_df['is_it'] = pd.Series([len(set(re.findall(r'\w+', t.lower())) & ITALIAN_MARK) >= 1 for t in it_df.title], index=it_df.index, dtype=bool)
n_title_dropped = int((~it_df.is_it).sum()); it_df = it_df[it_df.is_it]
left, right = it_df[it_df.leaning.isin(['left', 'centre_left'])], it_df[it_df.leaning.isin(['right', 'centre_right'])]
TW = pd.DataFrame(columns=['term', 'articles_left', 'articles_right', 'log_odds', 'z', 'side'])
if len(left) >= 10 and len(right) >= 10:
    cl, cr = termcount(left.title.map(title_tokens)), termcount(right.title.map(title_tokens)); TW = log_odds(cl, cr, termcount(it_df.title.map(title_tokens)), 5)
    TW = TW.rename(columns={'count_1': 'articles_left', 'count_2': 'articles_right'}); TW['side'] = np.where(TW.z > 0, 'left', 'right')
write_csv('logodds_title_words_italy_left_vs_right', TW)

# ---------- agreement ----------
KFIELDS = [('body', 'stance_protesters'), ('body', 'stance_demands'), ('body', 'protest_type'), ('head', 'headline_stance_protesters'), ('head', 'headline_frame')]
def kappa_rows(lab1, lab2, name):
    out = []
    for kind, f in KFIELDS:
        pairs = [(cat(lab1[(u, k)][1], f) if f in ENUM else None, cat(lab2[(u, k)][1], f)) for (u, k) in lab2 if k == kind and (u, k) in lab1]
        pairs = [p for p in pairs if p[0] and p[1]]
        if len(pairs) < 2: out.append(dict(comparison=name, field=f, n=len(pairs), kappa=np.nan, agreement=np.nan)); continue
        a, b = zip(*pairs); kap = cohen_kappa_score(a, b) if len(set(a) | set(b)) > 1 else np.nan
        out.append(dict(comparison=name, field=f, n=len(pairs), kappa=kap, agreement=float(np.mean([x == y for x, y in pairs]))))
    return out
KAP = pd.DataFrame(kappa_rows(labA, labB, 'modello A (Qwen3.8-27B) contro modello B (gpt-oss-120b)'))
claude_path = ROOT + '/data/claude_read.json'; claude_ready = os.path.exists(claude_path)
if claude_ready:
    cr = json.load(open(claude_path)); rows_c = []
    for kind, f in KFIELDS:
        pairs = [(cat(labA[(u, kind)][1], f), str(v[f]).strip().lower()) for u, v in cr.items() if f in v and (u, kind) in labA]
        pairs = [p for p in pairs if p[0] and p[1] in ENUM[f]]
        if len(pairs) < 2: rows_c.append(dict(comparison='modello A contro lettura di Claude', field=f, n=len(pairs), kappa=np.nan, agreement=np.nan)); continue
        a, b = zip(*pairs); rows_c.append(dict(comparison='modello A contro lettura di Claude', field=f, n=len(pairs), kappa=cohen_kappa_score(a, b) if len(set(a) | set(b)) > 1 else np.nan, agreement=float(np.mean([x == y for x, y in pairs]))))
    KAP = pd.concat([KAP, pd.DataFrame(rows_c)], ignore_index=True)
else: print('lettura di Claude vs modello A: not yet (data/claude_read.json missing)')
write_csv('agreement_kappa', KAP)

# ---------- cuts, parse failures, engines ----------
cut_rows, eng_rows = [], []
for name, st, eng, inv in (('A', statsA, engA, invA), ('B', statsB, engB, invB)):
    for kind in ('head', 'body'):
        cut_rows.append(dict(model=name, kind=kind, rows=st[(kind, 'rows')], parsed=st[(kind, 'ok')], unparseable=st[(kind, 'unparseable')], error_rows=st[(kind, 'error')], cut=st[(kind, 'cut')], longest_prompt_tokens=st[(kind, 'max_tokens')], window=SERVED_WINDOW))
    for e, c in eng.items(): eng_rows.append(dict(model=name, engine=e, rows=c))
    cut_rows.append(dict(model=name, kind='invalid_values', rows=sum(inv.values()), parsed=None, unparseable=None, error_rows=None, cut=None, longest_prompt_tokens=None, window=None))
CUT = pd.DataFrame(cut_rows); ENG = pd.DataFrame(eng_rows, columns=['model', 'engine', 'rows']); write_csv('cuts_and_parse', CUT); write_csv('engines', ENG)

# ---------- funnel, read from files ----------
def n_lines(p): return max(sum(1 for _ in opn(p)) - 1, 0) if os.path.exists(p) or os.path.exists(p + '.gz') else None
rel = {}
for f in ('relevance_qwen.jsonl', 'relevance_qwen2.jsonl'):
    for r in rows_of(ROOT + '/data/' + f):
        st, j = parse_raw(r.get('raw') or '')
        if st == 'ok': rel[r['url']] = (j.get('protest'), j.get('youth'))
framing_set = sum(1 for p, y in rel.values() if p == 1 and y == 1)
it_out = sorted({o for o in outlets_A if ledger.get(o, {}).get('country') == 'Italy'})
FUN = [('Testate nell\'elenco', len(ledger)), ('Testate con articoli raccolti (file in data/articles)', len(glob.glob(ROOT + '/data/articles/*.jsonl')) or None),
       ('Articoli raccolti (somma delle colonne del registro)', sum(int(r['articles'] or 0) for r in ledger.values())),
       ('Candidati del primo filtro a parole chiave', n_lines(ROOT + '/data/relevance_candidates.tsv')), ('Candidati del secondo filtro', n_lines(ROOT + '/data/relevance_candidates2.tsv')),
       ('Articoli etichettati per pertinenza', len(rel)), ('Su proteste (protest=1)', sum(1 for p, y in rel.values() if p == 1)), ('Su proteste giovanili (protest=1 e youth=1): insieme da analizzare', framing_set),
       ('Articoli già etichettati (titolo o testo) dal modello A', len(df)), ('Con etichetta del titolo', int(df.has_head.sum())), ('Con etichetta del testo', int(df.has_body.sum())),
       ('Testi analizzati (non troncati, non dirette)', int(df.body_ok.sum())), ('Di cui proteste nel paese della testata (copertura interna)', int((df.body_ok & (df.domestic == True)).sum())),
       ('Testi esclusi perché troncati (paywall o brevi)', int((df.has_body & df.trunc).sum())), ('Testi esclusi perché dirette (oltre %d caratteri)' % LIVE_BLOG_CHARS, int((df.has_body & df.live).sum()))]
FUNNEL = pd.DataFrame(FUN, columns=['step', 'n'], dtype=object); write_csv('funnel', FUNNEL)
n_it_art, n_ot_art = int((df.group == 'Italy').sum()), int((df.group == 'Others').sum())
out_summary = pd.DataFrame([dict(item='testate con etichette (Italia)', n=len(it_out)), dict(item='testate con etichette (altri)', n=len(outlets_A) - len(it_out)),
                            dict(item='testate senza orientamento abbinato', n=len(unmatched)), dict(item='articoli senza metadati (data, testo)', n=int((~df.has_meta).sum())),
                            dict(item='titoli non italiani scartati dall\'analisi delle parole', n=n_title_dropped)]); write_csv('coverage_counts', out_summary)

# ---------- SVG charts ----------
FONT_CSS = lambda: ''
def fnt(w=700, f='Barlow Condensed'): return 'font-family="%s" font-weight="%d"' % (f, w)
def T(x, y, s, size=22, fill=RED, anchor='start', w=700, f='Barlow Condensed', extra=''):
    return '<text x="%.1f" y="%.1f" font-size="%d" fill="%s" text-anchor="%s" %s %s>%s</text>' % (x, y, size, fill, anchor, fnt(w, f), extra, esc(s))
def HINT(hint):
    parts = hint.split(' · '); 
    if len(hint) <= 62: return T(60, 50, hint, 21, DARK, w=400, f='Barlow Semi Condensed')
    best = min(range(1, len(parts)), key=lambda i: abs(len(' · '.join(parts[:i])) - len(' · '.join(parts[i:])))) if len(parts) > 1 else 0
    l1, l2 = ' · '.join(parts[:best]), ' · '.join(parts[best:])
    return T(60, 44, l1, 21, DARK, w=400, f='Barlow Semi Condensed') + T(60, 72, l2, 21, DARK, w=400, f='Barlow Semi Condensed')
def svg_wrap(body, h=960, w=960): return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d"><rect width="%d" height="%d" fill="%s"/>%s</svg>' % (w, h, w, h, w, h, BG, body)
def empty_chart(msg, hint):
    return svg_wrap(HINT(hint) + T(480, 480, msg, 44, RED, 'middle'))
def rtop(x, y, w, h, kind, col):
    r = min(w / 2, h); st = 'fill="%s"' % col if kind != 'outline' else 'fill="none" stroke="%s" stroke-width="2.5"' % RED
    if h <= 0: return ''
    return '<path d="M%.1f,%.1f L%.1f,%.1f A%.1f,%.1f 0 0 1 %.1f,%.1f L%.1f,%.1f A%.1f,%.1f 0 0 1 %.1f,%.1f L%.1f,%.1f Z" %s/>' % (x, y + h, x, y + r, r, r, x + r, y, x + w - r, y, r, r, x + w, y + r, x + w, y + h, st)
def nice(ymax, parts=5):
    for s in (1, 2, 5, 10, 20, 25, 50, 100):
        if ymax / s <= parts: return s, math.ceil(ymax / s) * s
    return 100, 100
def whisker(x, y1, y2): return '<path d="M%.1f,%.1f V%.1f M%.1f,%.1f H%.1f M%.1f,%.1f H%.1f" stroke="%s" stroke-width="1.6" fill="none"/>' % (x, y1, y2, x - 6, y1, x + 6, x - 6, y2, x + 6, DARK)
def legend(items, y, xr=920):
    out, x = [], xr
    for lab, kind, col in reversed(items):
        wlab = len(lab) * 12.5 + 38; x -= wlab
        out.append(T(x, y, lab, 24, col if kind != 'outline' else RED))
        out.append('<circle cx="%.1f" cy="%.1f" r="9" %s/>' % (x + len(lab) * 12.5 + 14, y - 8, ('fill="%s"' % col) if kind != 'outline' else 'fill="none" stroke="%s" stroke-width="2.5"' % RED)); x -= 20
    return ''.join(out)
def grouped_bars(cats, leg, hint, panels=None, ymax_hint=None, unit='%'):
    """cats: [dict(label=[lines], bars=[dict(est,lo,hi,n,kind,col)])]  values as shares 0-1"""
    vals = [b['hi'] if b['hi'] == b['hi'] else b['est'] for c in cats for b in c['bars'] if b['est'] == b['est']]
    if not vals: return empty_chart('DATI IN ARRIVO', hint)
    step, ymax = nice(max(vals) * 100 * 1.05); ymax = min(ymax, 100) if unit == '%' and max(vals) <= 1 else ymax; x0, x1, yt, yb = 100, 920, 150, 700; gw = (x1 - x0) / len(cats); out = [HINT(hint)]
    sc = lambda v: yb - (yb - yt) * v * 100 / ymax
    for t in range(0, int(ymax) + 1, step):
        y = sc(t / 100); out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>' % (x0, x1, y, y, GRID)); out.append(T(x0 - 12, y + 7, '%d%s' % (t, unit), 20, '#1a1a1a', 'end', 400, 'Barlow Semi Condensed'))
    for gi, c in enumerate(cats):
        nb = len(c['bars']); bw = min(96, gw * 0.78 / nb); gx = x0 + gi * gw + (gw - bw * nb) / 2
        for bi, b in enumerate(c['bars']):
            bx = gx + bi * bw
            if b['est'] == b['est']:
                out.append(rtop(bx, sc(b['est']), bw, yb - sc(b['est']), b['kind'], b['col']))
                if b['lo'] == b['lo']: out.append(whisker(bx + bw / 2, sc(b['lo']), sc(b['hi'])))
            out.append(T(bx + bw / 2, yb + 26, 'n=' + it(b['n']), 19, DARK, 'middle', 400, 'Barlow Semi Condensed'))
        for li, line in enumerate(c['label']): out.append(T(x0 + gi * gw + gw / 2, yb + 62 + 28 * li, line, 25, RED, 'middle'))
    out.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s" stroke-width="2"/>' % (x0, x1, yb, yb, DARK)); out.append(legend(leg, 905))
    return svg_wrap(''.join(out))
def hbars(rows, hint, k=100, suf='%', lab=None, fixed_rh=None):
    """rows: dict(label,est,lo,hi,n,kind,col,bold) or dict(header=text)"""
    real = [r for r in rows if 'header' not in r and r['est'] == r['est']]
    if not real: return empty_chart('DATI IN ARRIVO', hint)
    xmax = max([(r['hi'] if r['hi'] == r['hi'] else r['est']) for r in real]) * k * 1.08
    if xmax <= 0: return empty_chart('DATI IN ARRIVO', hint)
    step, xmax = nice(xmax); xmax = min(xmax, 100) if suf == '%' else xmax
    rh = fixed_rh or min(34, 760 / max(len(rows), 1)); H = int(max(960, 130 + rh * len(rows) + 90)); lx, bx0, bx1 = 270, 285, 800
    sc = lambda v: bx0 + (bx1 - bx0) * v * k / xmax; out = [HINT(hint)]
    for t in range(0, int(xmax) + 1, step):
        out.append('<line x1="%.1f" x2="%.1f" y1="105" y2="%d" stroke="%s" stroke-width="1"/>' % (sc(t / k), sc(t / k), 110 + rh * len(rows), GRID)); out.append(T(sc(t / k), 98, '%d%s' % (t, suf), 19, '#1a1a1a', 'middle', 400, 'Barlow Semi Condensed'))
    for i, r in enumerate(rows):
        y = 120 + rh * i
        if 'header' in r: out.append(T(60, y + rh * 0.7, r['header'], 24, DARK)); continue
        if r['est'] != r['est']: continue
        bh = rh * 0.62; sz = 22 if r.get('bold') else 19
        out.append(T(lx, y + rh * 0.68, r['label'], sz + 2, RED if r.get('bold') else DARK, 'end'))
        if r['kind'] == 'outline': out.append('<rect x="%d" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="none" stroke="%s" stroke-width="2"/>' % (bx0, y + rh * 0.19, sc(r['est']) - bx0, bh, bh / 2, RED))
        else: out.append('<rect x="%d" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s"/>' % (bx0, y + rh * 0.19, max(sc(r['est']) - bx0, 1), bh, bh / 2, r['col']))
        if r['lo'] == r['lo']: out.append('<path d="M%.1f,%.1f H%.1f M%.1f,%.1f v%.1f M%.1f,%.1f v%.1f" stroke="%s" stroke-width="1.6"/>' % (sc(r['lo']), y + rh * 0.5, sc(r['hi']), sc(r['lo']), y + rh * 0.3, rh * 0.4, sc(r['hi']), y + rh * 0.3, rh * 0.4, DARK))
        tx = max(sc(r['hi']) if r['hi'] == r['hi'] else sc(r['est']), sc(r['est'])) + 8
        out.append(T(tx, y + rh * 0.66, '%s · n=%s' % ((lab or pct)(r['est']), it(r['n'])), 17, DARK, 'start', 400, 'Barlow Semi Condensed'))
    out.append('<line x1="%d" x2="%d" y1="105" y2="%d" stroke="%s" stroke-width="2"/>' % (bx0, bx0, 110 + rh * len(rows), DARK)); return svg_wrap(''.join(out), H)
def line_chart(weeks, series, hint):
    if not weeks or not any(p['est'] == p['est'] for s in series for p in s['pts']): return empty_chart('DATI IN ARRIVO', hint)
    vals = [p['est'] for s in series for p in s['pts'] if p['est'] == p['est']]; step, ymax = nice(max(vals) * 100 * 1.1); ymax = min(ymax, 100); x0, x1, yt, yb = 100, 840, 150, 700
    sc = lambda v: yb - (yb - yt) * v * 100 / ymax; px = lambda i: x0 + (x1 - x0) * (i / max(len(weeks) - 1, 1)) if len(weeks) > 1 else (x0 + x1) / 2
    out = [HINT(hint)]
    for t in range(0, int(ymax) + 1, step):
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s"/>' % (x0, x1, sc(t / 100), sc(t / 100), GRID)); out.append(T(x0 - 12, sc(t / 100) + 7, '%d%%' % t, 20, '#1a1a1a', 'end', 400, 'Barlow Semi Condensed'))
    mon = ['GEN', 'FEB', 'MAR', 'APR', 'MAG', 'GIU', 'LUG', 'AGO', 'SET', 'OTT', 'NOV', 'DIC']
    for i, w in enumerate(weeks):
        d = dt.date.fromisoformat(w); out.append(T(px(i), yb + 34, '%d %s' % (d.day, mon[d.month - 1]), 22, RED, 'middle'))
        for si, s in enumerate(series): out.append(T(px(i), yb + 62 + 22 * si, 'n=' + it(s['pts'][i]['n']), 17, DARK, 'middle', 400, 'Barlow Semi Condensed'))
    for s in sorted(series, key=lambda s: s['thick']):
        pts = [(px(i), sc(p['est'])) for i, p in enumerate(s['pts']) if p['est'] == p['est']]
        if len(pts) > 1: out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s"/>' % (' '.join('%.1f,%.1f' % p for p in pts), s['col'], 6 if s['thick'] else 2.5))
        for x, y in pts:
            out.append('<circle cx="%.1f" cy="%.1f" r="%d" fill="%s"/>' % (x, y, 9 if s['thick'] else 5, s['col']) if not s['thick'] else '<circle cx="%.1f" cy="%.1f" r="10" fill="%s" stroke="%s" stroke-width="3"/><circle cx="%.1f" cy="%.1f" r="4" fill="%s"/>' % (x, y, BG, s['col'], x, y, s['col']))
        if pts: out.append(T(pts[-1][0] + 16, pts[-1][1] + 7, s['label'], 24, s['col']))
    out.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s" stroke-width="2"/>' % (x0, x1, yb, yb, DARK)); return svg_wrap(''.join(out))

def gsel(view, metric, group):
    s = GT[(GT.view == view) & (GT.metric == metric) & (GT.group == group)]
    return s.iloc[0].to_dict() if len(s) else dict(est=np.nan, lo=np.nan, hi=np.nan, n=0, n_outlets=0, n_articles=0)
def bar(view, metric, group, kind, col): g = gsel(view, metric, group); return dict(est=g['est'], lo=g['lo'], hi=g['hi'], n=g['n'], kind=kind, col=col)
UP = 'PIÙ ALTO = PIÙ OSTILE · % DI ARTICOLI'
charts = {}
charts['c1_ostili_italia_altri'] = grouped_bars([dict(label=['TUTTA LA COPERTURA'], bars=[bar('all', 'hostile', 'Italy', 'solid', RED), bar('all', 'hostile', 'Others', 'outline', RED)]),
    dict(label=['SOLO PROTESTE NEL', 'PROPRIO PAESE'], bars=[bar('domestic', 'hostile', 'Italy', 'solid', RED), bar('domestic', 'hostile', 'Others', 'outline', RED)])],
    [('ITALIA', 'solid', RED), ('ALTRI PAESI', 'outline', RED)], 'ARTICOLI OSTILI VERSO I MANIFESTANTI · PIÙ ALTO = PIÙ OSTILE · % DEGLI ARTICOLI · BARRA = INTERVALLO 95%')
cats2 = []
for view, lab in (('all', ['TUTTA LA COPERTURA']), ('domestic', ['PROTESTE NEL PROPRIO PAESE'])):
    cats2.append(dict(label=lab + ['ITALIA'], bars=[bar(view, 'viol', 'Italy', 'solid', RED), bar(view, 'dem', 'Italy', 'solid', SAL)]))
    cats2.append(dict(label=['ALTRI PAESI'], bars=[bar(view, 'viol', 'Others', 'solid', RED), bar(view, 'dem', 'Others', 'solid', SAL)]))
charts['c2_violenza_richieste'] = grouped_bars(cats2, [('FRASI SULLA VIOLENZA', 'solid', RED), ('FRASI SULLE RICHIESTE', 'solid', SAL)], 'QUOTA MEDIA DELLE FRASI DI UN ARTICOLO · PIÙ VIOLENZA, MENO RICHIESTE = PIÙ PEGGIO · BARRA = INTERVALLO 95%')
DOT_MIN = 50   # countries under this many articles go into one row "altri paesi (meno di 50 articoli)"
def dot_panel(view, x0, w, y0, rh, rows, title):
    g = lambda grp: gsel(view, 'hostile', grp); it_ = g('Italy'); out = [T(x0, y0 - 40, title, 22, DARK)]
    data = []
    for c in sorted({r for r in GT[GT.view == view].group.unique() if r not in ('Italy', 'Others', 'Small')} | {'Italy'}):
        e = g(c)
        if e['est'] == e['est'] and (e['n'] >= DOT_MIN or c == 'Italy'): data.append((itn(c).upper(), e, c == 'Italy'))
    sm = g('Small')
    if sm['est'] == sm['est'] and sm['n'] > 0: data.append(('ALTRI PAESI (SOTTO %d TESTI)' % DOT_MIN, sm, False))
    return data
def dot_chart(hint):
    panels = [dot_panel(v, 0, 0, 0, 0, None, '') for v in ('all', 'domestic')]
    names = sorted({d[0] for p in panels for d in p}, key=lambda n: -max([d[1]['est'] for p in panels for d in p if d[0] == n and d[1]['est'] == d[1]['est']] or [0]))
    small = 'ALTRI PAESI (SOTTO %d TESTI)' % DOT_MIN; names = [n for n in names if n != small] + [small]
    if len(names) < 3: return empty_chart('DATI IN ARRIVO', hint)
    rh, y0, lx, pw, gap = 30, 150, 300, 250, 40; H = int(y0 + rh * len(names) + 70); out = [HINT(hint)]
    for pi_, (v, tt) in enumerate((('all', 'TUTTA LA COPERTURA'), ('domestic', 'SOLO PROTESTE NEL PROPRIO PAESE'))):
        x0 = lx + pi_ * (pw + gap + 40); sc = lambda q: x0 + pw * q; byname = {d[0]: d for d in panels[pi_]}; ita = byname.get('ITALIA', (None, dict(est=np.nan, lo=np.nan, hi=np.nan, n=0), True))[1]
        out.append(T(x0, y0 - 30, tt, 21, DARK))
        for t in (0, .25, .5, .75, 1.0):
            out.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-width="1"/>' % (sc(t), sc(t), y0 - 8, y0 + rh * len(names), GRID)); out.append(T(sc(t), y0 - 12, '%d%%' % (t * 100), 16, DARK, 'middle', 400, 'Barlow Semi Condensed'))
        if ita['est'] == ita['est']:
            if ita['lo'] == ita['lo']: out.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s" opacity="0.18"/>' % (sc(ita['lo']), y0 - 8, sc(ita['hi']) - sc(ita['lo']), rh * len(names) + 8, RED))
            out.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-width="1.5" stroke-dasharray="4 3"/>' % (sc(ita['est']), sc(ita['est']), y0 - 8, y0 + rh * len(names), RED))
        for i, n in enumerate(names):
            y = y0 + rh * i + rh / 2
            if v == 'all': out.append(T(lx - 12, y + 6, n, 20 if n == 'ITALIA' else 18, RED if n == 'ITALIA' else DARK, 'end'))
            d = byname.get(n)
            if not d or d[1]['est'] != d[1]['est']: out.append(T(sc(0) + 6, y + 5, 'meno di %d testi' % DOT_MIN, 14, GRID, 'start', 400, 'Barlow Semi Condensed')); continue
            e = d[1]; col = RED if d[2] else DARK
            if e['lo'] == e['lo']: out.append('<path d="M%.1f,%.1f H%.1f" stroke="%s" stroke-width="2"/>' % (sc(e['lo']), y, sc(e['hi']), col))
            out.append('<circle cx="%.1f" cy="%.1f" r="%d" fill="%s"/>' % (sc(e['est']), y, 7 if d[2] else 5, col))
            out.append(T(sc(1.0) + 8, y + 5, 'n=%s' % it(e['n']), 14, '#7a7a7a', 'start', 400, 'Barlow Semi Condensed'))
    return svg_wrap(''.join(out), H, 960 + 0) if False else '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d"><rect width="%d" height="%d" fill="%s"/>%s</svg>' % (1100, H, 1100, H, 1100, H, BG, ''.join(out))
charts['c3_paesi'] = dot_chart('UNA RIGA = I GIORNALI DI UN PAESE · PUNTO = % DI ARTICOLI OSTILI VERSO I MANIFESTANTI · LINEA = INTERVALLO 95% · FASCIA ROSSA = ITALIA')
def pair_chart(view, hint):
    dd = VIEWS[view]; bi = boot(dd[dd.group == 'Italy'], view + 'Italy'); i = MK.index('hostile'); rows = []; pairs = []
    cs = dd.groupby('country').size()
    for c in cs[cs >= MINN].index:
        if c == 'Italy' or bi is None: continue
        bc = boot(dd[dd.country == c], view + c); lo_i, hi_i = ci(bi, i); lo_c, hi_c = ci(bc, i)
        dif = bi['reps'][:, i] - bc['reps'][:, i]; dif = dif[~np.isnan(dif)]
        lo, hi = (np.percentile(dif, 2.5), np.percentile(dif, 97.5)) if len(dif) > 100 and bc['k'] > 1 and bi['k'] > 1 else (np.nan, np.nan)
        pairs.append((bi['est'][i] - bc['est'][i], c, lo, hi, dict(est=bi['est'][i], lo=lo_i, hi=hi_i, n=bi['n'][i]), dict(est=bc['est'][i], lo=lo_c, hi=hi_c, n=bc['n'][i])))
    for dif, c, lo, hi, a, b in sorted(pairs, key=lambda x: -x[0]):
        rows.append(dict(header='ITALIA – %s: %s PUNTI (DA %s A %s)' % (itn(c).upper(), pp(dif), pp(lo), pp(hi))))
        rows.append(dict(label='ITALIA', kind='solid', col=RED, bold=True, **a)); rows.append(dict(label=itn(c).upper(), kind='solid', col=SAL, **b))
    return None, pairs
for view, key, tag in (('all', 'c6_italia_vs_paese_tutta', 'TUTTA LA COPERTURA'), ('domestic', 'c6_italia_vs_paese_casa', 'SOLO PROTESTE NEL PROPRIO PAESE')):
    _, PAIRS = pair_chart(view, 'ITALIA CONTRO OGNI PAESE · ARTICOLI OSTILI · %s · BARRA = INTERVALLO 95%% (TESTATE RICAMPIONATE)' % tag)
    write_csv(key, pd.DataFrame([dict(country=c, diff=d, lo=l, hi=h, italy=a['est'], italy_n=a['n'], other=b['est'], other_n=b['n']) for d, c, l, h, a, b in PAIRS]))
weeks = sorted(w for w in WT.week.unique() if w) if len(WT) else []
def wpt(side, w, metric='hostile'):
    s = WT[(WT.side == side) & (WT.week == w) & (WT.metric == metric)]
    if not len(s) or s.iloc[0].n < 20: return dict(est=np.nan, n=int(s.iloc[0].n) if len(s) else 0)
    return dict(est=s.iloc[0].est, n=int(s.iloc[0].n))
charts['c4_settimane'] = line_chart(weeks, [dict(label='ITALIA', col=RED, thick=True, pts=[wpt('Italy', w) for w in weeks]), dict(label='ALTRI', col=BLK, thick=False, pts=[wpt('Others', w) for w in weeks])],
    'ARTICOLI OSTILI PER SETTIMANA (DAL LUNEDÌ) · PIÙ ALTO = PIÙ OSTILE · % DEGLI ARTICOLI · PUNTI SOLO CON n≥20')
LORDER = ['far_left', 'left', 'centre_left', 'centre', 'centre_right', 'right', 'far_right', 'public_broadcaster', 'wire', 'unclassified', 'unknown']
LNAME = {'far_left': 'ESTREMA SINISTRA', 'left': 'SINISTRA', 'centre_left': 'CENTRO-SINISTRA', 'centre': 'CENTRO', 'centre_right': 'CENTRO-DESTRA', 'right': 'DESTRA', 'far_right': 'ESTREMA DESTRA',
         'public_broadcaster': 'SERVIZIO PUBBLICO', 'wire': 'AGENZIE', 'unclassified': 'NON CLASSIFICATE', 'unknown': 'SENZA FONTE'}
def lsel(view, side, lv, metric='hostile'):
    s = LT[(LT.view == view) & (LT.side == side) & (LT.leaning == lv) & (LT.metric == metric)] if len(LT) else []
    return s.iloc[0].to_dict() if len(s) else dict(est=np.nan, lo=np.nan, hi=np.nan, n=0, n_articles=0)
lcats = []
for lv in LORDER:
    a, b = lsel('all', 'Italy', lv), lsel('all', 'Others', lv)
    if a['n'] >= MINN and b['n'] >= MINN:
        mk = lambda g, kind: dict(est=g['est'] if g['n'] >= MINN else np.nan, lo=g['lo'] if g['n'] >= MINN else np.nan, hi=g['hi'] if g['n'] >= MINN else np.nan, n=g['n'], kind=kind, col=RED)
        lcats.append(dict(label=(LNAME.get(lv, lv.upper()).replace('-', '- ', 1).split(' ', 1) if len(LNAME.get(lv, lv)) > 8 else [LNAME.get(lv, lv.upper())]), bars=[mk(a, 'solid'), mk(b, 'outline')]))
charts['c5_orientamento'] = grouped_bars(lcats, [('ITALIA', 'solid', RED), ('ALTRI PAESI', 'outline', RED)], 'ARTICOLI OSTILI PER ORIENTAMENTO DELLA TESTATA · PIÙ ALTO = PIÙ OSTILE · %% DEGLI ARTICOLI (n≥%d)' % MINN)
wrow = []
for side, name, col in (('Italy', 'PIÙ FREQUENTI IN ITALIA', RED), ('Others', 'PIÙ FREQUENTI ALTROVE', SAL)):
    wrow.append(dict(header=name))
    for _, r in LOD[LOD.side == side].sort_values('z', ascending=(side == 'Others')).head(10).iterrows():
        wrow.append(dict(label=r.term[:28], est=abs(r.z), lo=np.nan, hi=np.nan, n=int(r.articles_italy if side == 'Italy' else r.articles_others), kind='solid', col=col))
charts['c6_parole_delegittimanti'] = hbars(wrow, 'TERMINI DELEGITTIMANTI PIÙ DISTINTIVI · LUNGHEZZA = PUNTEGGIO z (LOG-ODDS CON PRIOR INFORMATIVO) · n = ARTICOLI', k=1, suf='', lab=lambda x: 'z=' + it(x, 1))
for k, s in charts.items():
    atomic('%s/charts/%s.svg' % (R, k), s)
    import cairosvg; cairosvg.svg2png(bytestring=s.encode(), write_to='%s/charts/%s.png' % (R, k), output_width=1920)

# ---------- Italian prose from the numbers ----------
def D(view, m):
    s = DT[(DT.view == view) & (DT.metric == m)]
    return s.iloc[0].to_dict() if len(s) else dict(italy=np.nan, others=np.nan, diff=np.nan, lo=np.nan, hi=np.nan, n_italy=0, n_others=0)
def verdict(d, more, less, same='non si distingue da'):
    if d['lo'] != d['lo']: return 'dati insufficienti per confrontare'
    return more if d['lo'] > 0 else less if d['hi'] < 0 else same
def vsent(view, m, subj, more, less, same, what):
    d = D(view, m)
    if min(d['n_italy'], d['n_others']) < MINN: return 'Dati ancora parziali: %s non è confrontabile finché ogni gruppo ha almeno %d articoli (Italia n=%s, altri paesi n=%s).' % (what, MINN, it(d['n_italy']), it(d['n_others']))
    return '%s %s: %s contro %s (differenza %s punti, intervallo al 95%% da %s a %s; n=%s contro n=%s).' % (subj, verdict(d, more, less, same), pct(d['italy']), pct(d['others']), pp(d['diff']), pp(d['lo']), pp(d['hi']), it(d['n_italy']), it(d['n_others']))
S = {}
S['h1'] = vsent('all', 'hostile', 'Nella copertura delle proteste giovanili i giornali italiani sono', 'più ostili verso i manifestanti degli altri paesi', 'meno ostili verso i manifestanti degli altri paesi', 'ostili verso i manifestanti in misura che non si distingue da quella degli altri paesi', 'la quota di articoli ostili')
dv, dd_ = D('all', 'viol'), D('all', 'dem')
S['h2'] = ('Le frasi sulla violenza sono %s in Italia contro %s altrove (%s punti; da %s a %s); quelle sulle richieste dei manifestanti %s contro %s (%s punti; da %s a %s).' % (pct(dv['italy']), pct(dv['others']), pp(dv['diff']), pp(dv['lo']), pp(dv['hi']), pct(dd_['italy']), pct(dd_['others']), pp(dd_['diff']), pp(dd_['lo']), pp(dd_['hi']))
           + ' Rispetto agli altri paesi la quota di violenza %s e quella di richieste %s.' % (verdict(dv, 'è più alta', 'è più bassa', 'non si distingue'), verdict(dd_, 'è più alta', 'è più bassa', 'non si distingue'))) if min(dv['n_italy'], dv['n_others']) >= MINN else 'Dati ancora parziali sulle quote di frasi (violenza, richieste).'
S['c1'] = vsent('domestic', 'hostile', 'Se si guardano solo le proteste nel paese della testata, i giornali italiani sono', 'più ostili degli altri paesi', 'meno ostili degli altri paesi', 'ostili in misura che non si distingue da quella degli altri paesi', 'la quota di articoli ostili sulle proteste in casa')
d1 = D('all', 'ratio'); d2 = D('domestic', 'ratio')
S['c2'] = ('Rapporto tra frasi di violenza e frasi di richieste: Italia %s, altri paesi %s su tutta la copertura (intervallo della differenza da %s a %s); sulle proteste in casa %s contro %s.' % (it(d1['italy'], 2), it(d1['others'], 2), it(d1['lo'], 2).replace('-', '−'), it(d1['hi'], 2).replace('-', '−'), it(d2['italy'], 2), it(d2['others'], 2))) if min(d1['n_italy'], d1['n_others']) >= MINN and min(d2['n_italy'], d2['n_others']) >= MINN else 'Dati ancora parziali sul rapporto violenza / richieste.'
cs = GT[(GT.view == 'all') & (GT.metric == 'hostile') & (GT.n >= DOT_MIN) & (~GT.group.isin(['Italy', 'Others', 'Small']))]
if len(cs) and gsel('all', 'hostile', 'Italy')['n'] >= MINN:
    it_est = gsel('all', 'hostile', 'Italy')['est']; rank = int((cs.est > it_est).sum()) + 1
    S['c3'] = 'Con almeno %d articoli con testo analizzato ci sono %d paesi oltre all\'Italia; l\'Italia è al posto %d su %d per quota di articoli ostili (%s); gli intervalli tra paesi si sovrappongono quando le barre si sfiorano, quindi l\'ordine tra paesi vicini non è dimostrato.' % (DOT_MIN, len(cs), rank, len(cs) + 1, pct(it_est))
else: S['c3'] = 'Dati ancora parziali: pochi paesi hanno almeno %d articoli analizzati.' % MINN
hw = [(w, wpt('Italy', w)['est'], wpt('Others', w)['est']) for w in weeks]; hw = [h for h in hw if h[1] == h[1] and h[2] == h[2]]
S['c4'] = ('Settimana per settimana, la quota di articoli ostili in Italia è sopra quella degli altri paesi in %d settimane su %d con dati (n≥20 per gruppo); ' % (sum(h[1] > h[2] for h in hw), len(hw)) + 'il punto più alto in Italia è %s nella settimana del %s.' % (pct(max(h[1] for h in hw)), dt.date.fromisoformat(max(hw, key=lambda h: h[1])[0]).strftime('%d/%m'))) if hw else 'Dati ancora parziali: nessuna settimana ha almeno 20 articoli per gruppo.'
lp = [(lv, lsel('all', 'Italy', lv), lsel('all', 'Others', lv)) for lv in LORDER]; lp = [(lv, a, b) for lv, a, b in lp if a['n'] >= MINN and b['n'] >= MINN]
if lp:
    parts = []
    for lv, a, b in lp:
        lo, hi = (np.nan, np.nan)
        parts.append('%s: Italia %s (n=%s), altri %s (n=%s)' % (LNAME[lv].lower(), pct(a['est']), it(a['n']), pct(b['est']), it(b['n'])))
    S['c5'] = 'A parità di orientamento della testata: ' + '; '.join(parts[:5]) + '.'
else: S['c5'] = 'Dati ancora parziali: nessun orientamento ha almeno %d articoli sia in Italia sia negli altri paesi.' % MINN
nm = len(df)
S['status'] = ('Stato dei dati: %s articoli etichettati su %s dell\'insieme da analizzare (%s%%); testi analizzati %s; Italia %s articoli, altri paesi %s.' % (it(nm), it(framing_set), it(100 * nm / framing_set, 1) if framing_set else 'n.d.', it(int(df.body_ok.sum())), it(n_it_art), it(n_ot_art)))+(' Etichettatura del modello A completa: gli altri articoli dell\'insieme sono fuori dalla finestra delle date o senza titolo.' if nm >= 0.99 * framing_set else ' Il rapporto va rigenerato quando le etichette sono complete.')
n_countries = df[df.country != 'Italy'].country.nunique()

# ---------- HTML ----------
def b64(p): return base64.b64encode(open(p, 'rb').read()).decode()
fonts = ''.join('@font-face{font-family:"%s";font-weight:%d;src:url(data:font/ttf;base64,%s) format("truetype");}' % (fam, w, b64('%s/design/fonts/%s-%d.ttf' % (ROOT, fn, w))) for fam, fn, w in
                (('Barlow Condensed', 'BarlowCondensed', 400), ('Barlow Condensed', 'BarlowCondensed', 700), ('Barlow Semi Condensed', 'BarlowSemiCondensed', 400), ('EB Garamond', 'EBGaramond', 400)) if os.path.exists('%s/design/fonts/%s-%d.ttf' % (ROOT, fn, w)))
CSS = fonts + '''
:root{--bg:#EEE7D7;--red:#C1443F;--sal:#DB9D87;--ink:#1a1a1a;--dark:#323232}
*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;background:var(--bg);color:var(--ink);font-family:"EB Garamond",Georgia,serif;font-size:20px;line-height:1.5;-webkit-print-color-adjust:exact;print-color-adjust:exact}
main{max-width:740px;margin:0 auto;padding:32px 16px 64px}
.logo{font-family:"Barlow Condensed",Arial,sans-serif;font-weight:700;letter-spacing:.04em;color:#323232;font-size:26px;text-transform:uppercase}.logo i{font-style:normal;color:#D23737}
h1{font-family:"Barlow Condensed",Arial,sans-serif;font-weight:700;font-size:44px;line-height:1.05;margin:.5em 0 .3em}
h2{font-family:"Barlow Condensed",Arial,sans-serif;font-weight:700;font-size:28px;color:var(--red);text-transform:uppercase;margin:1.8em 0 .3em}
.answer{font-size:24px;line-height:1.35;margin:.4em 0 1em}.answer p{margin:.4em 0}
.status{font-family:"Barlow Semi Condensed",Arial,sans-serif;font-size:16px;color:var(--dark);border-left:4px solid var(--red);padding-left:10px}
figure{margin:1.2em 0 1.4em;page-break-inside:avoid}figcaption{font-size:18px;margin-bottom:.4em}figure svg,figure img{width:100%;height:auto;display:block}
.line{margin:.3em 0 0}
.box{border:1.5px solid var(--red);padding:6px 18px 10px;margin:1.4em 0;font-size:18px;line-height:1.4}.box h2{margin-top:.6em}.box ul{padding-left:20px}
table{border-collapse:collapse;font-family:"Barlow Semi Condensed",Arial,sans-serif;font-size:16px;width:100%;margin:.6em 0}th,td{padding:3px 8px;text-align:left;border-bottom:1px solid #B8AEB0}th{color:var(--red);font-family:"Barlow Condensed",Arial,sans-serif;text-transform:uppercase;font-size:17px}td.n{text-align:right}
.en{font-size:18px}
@page{size:A4;margin:16mm 14mm;background:#EEE7D7}
@media(max-width:560px){h1{font-size:34px}body{font-size:18px}}
'''
def table_html(df_, cols, heads, fmt):
    h = '<table><tr>' + ''.join('<th>%s</th>' % esc(x) for x in heads) + '</tr>'
    for _, r in df_.iterrows(): h += '<tr>' + ''.join('<td class="%s">%s</td>' % ('n' if i else '', esc(fmt[i](r[c]) if fmt[i] else r[c])) for i, c in enumerate(cols)) + '</tr>'
    return h + '</table>'
PL = open(ROOT + '/PLAN.md').read(); meas = re.search(r'Measured:[^\n]*', PL); measured = meas.group(0) if meas else 'n.d.'
reread = re.search(r'Full article text[^\n]*', PL)
lim = [l[2:].strip() for l in open(R + '/limitations_it.md') if l.startswith('- ')]
cutA = int(CUT[(CUT.model == 'A') & CUT.kind.isin(['head', 'body'])].cut.sum()); cutB = int(CUT[(CUT.model == 'B') & CUT.kind.isin(['head', 'body'])].cut.sum())
unp = CUT[CUT.kind.isin(['head', 'body'])]; wins = int(CUT[CUT.kind == 'body'].longest_prompt_tokens.max() or 0)
methods = ['<li>Modelli: Qwen3.8-27B in BF16 (modello A, tutti gli articoli) e gpt-oss-120b in MXFP4 come rilasciato (modello B, campione per l\'accordo, %s righe). Nessuna quantizzazione aggiunta da noi.</li>' % it(len(rowsB)),
           '<li>Temperatura %d. Un prompt fisso per ogni tipo di chiamata (titolo, testo). Finestra servita: %s token. Righe tagliate: modello A %s, modello B %s; prompt più lungo del testo: %s token.</li>' % (TEMPERATURE, it(SERVED_WINDOW), it(cutA), it(cutB), it(wins)),
           '<li>Righe non interpretabili (JSON non leggibile): modello A %s, modello B %s; chiamate andate in errore e poi rifatte con lo stesso prompt (righe con errore nel file: A %s, B %s; chiamate senza etichetta leggibile alla fine: %s). Valori fuori elenco ignorati: A %s, B %s.</li>' % (it(int(CUT[(CUT.model == 'A')].unparseable.sum())), it(int(CUT[(CUT.model == 'B')].unparseable.sum())), it(int(CUT[(CUT.model == 'A')].error_rows.sum())), it(int(CUT[(CUT.model == 'B')].error_rows.sum())), it(len({(r['url'], r['kind']) for r in rowsA} - set(labA))), it(sum(invA.values())), it(sum(invB.values()))),
           '<li>Cammino degli articoli: ' + '; '.join('%s: %s' % (esc(r.step), it(r.n)) for r in FUNNEL.itertuples() if r.n is not None) + '.</li>',
           '<li>Pertinenza, da PLAN.md: %s</li>' % esc(measured),
           '<li>Campione di lettura di Claude: %s articoli italiani e %s di altri paesi (seme %s). Campione per l\'accordo tra modelli: %s italiani e %s altri (seme %s).</li>' % (it(CLAUDE_SAMPLE['italian']), it(CLAUDE_SAMPLE['other']), CLAUDE_SAMPLE['seed'], it(KAPPA_SAMPLE['italian']), it(KAPPA_SAMPLE['other']), KAPPA_SAMPLE['seed']),
           '<li>Intervalli: ricampionamento delle testate (%s ripetizioni, seme %d), 95%%; le quote sono calcolate sul numero di articoli indicato come n. Un paese compare solo con almeno %d articoli. Finestra: %s / %s.</li>' % (it(BOOT), SEED, MINN, WINDOW[0], WINDOW[1]),
           '<li>Popolazione: articoli con etichetta in data/framing_A.jsonl. Le misure sul testo escludono testi troncati (meno di %s caratteri o a pagamento), dirette (oltre %s caratteri) e articoli duplicati nella stessa testata. Vista «in casa»: la protesta si svolge nel paese della testata (campo protest_country del modello). Orientamento: per le testate italiane vale la classificazione di Luca Bagnariol (2026-10-30, comunicata da Ruggero Lazzaroni); dove differisce dal valore con fonte (Il Sole 24 Ore: da centro-destra a centro; Panorama: da centro-destra a destra) si usa la sua, e i valori con fonte restano nel file csv/leaning_italy.csv; testate abbinate per dominio, %s su %s senza fonte abbinata.</li>' % (it(PAYWALL_MIN_CHARS), it(LIVE_BLOG_CHARS), it(len(unmatched)), it(len(outlets_A)))]
BIAS = open(R + '/csv/bias_test_output.txt').read().strip() if os.path.exists(R + '/csv/bias_test_output.txt') else ''
_m = re.findall(r'(Italia|altri paesi)\s+n=(\d+) \| accordo [\d.]+% kappa [\d.]+ \| ostili: modello ([\d.]+)%, Claude ([\d.]+)%', BIAS.split('contro lettura di Claude')[-1]) if BIAS else []
S['caveat'] = ('Attenzione: il modello giudica ostili più articoli della lettura di Claude, da cui è controllato. Su 200 articoli italiani: modello %s%%, Claude %s%%; su %s di altri paesi: modello %s%%, Claude %s%%. La differenza tra Italia e altri paesi regge anche sulle etichette di Claude, ma il livello assoluto delle quote qui sopra è probabilmente alto.' % (_m[0][2].replace('.', ','), _m[0][3].replace('.', ','), _m[1][1], _m[1][2].replace('.', ','), _m[1][3].replace('.', ','))) if len(_m) == 2 else ''
kap_html = table_html(KAP, ['comparison', 'field', 'n', 'kappa', 'agreement'], ['Confronto', 'Campo', 'n', 'kappa di Cohen', 'Accordo'], [None, None, lambda x: it(x), lambda x: it(x, 2), pct]) if len(KAP) else ''
if BIAS: kap_html += '<h2 style="margin-top:.8em">Prova sul prompt e confronto con Claude, per Italia e altri paesi</h2><p class="line">Prova: nel prompt del testo il modello leggeva il paese della testata. Lo abbiamo tolto, e in un secondo giro scambiato (Italia con un altro paese a caso, gli altri con Italia), su 598 articoli (il campione dell\'accordo tra modelli). Sotto, il risultato del programma analysis/bias_test.py. Il modello giudica più articoli ostili di Claude, in Italia e altrove: la differenza tra i gruppi regge, il livello assoluto è probabilmente alto.</p><pre style="white-space:pre-wrap;font-size:.8em">%s</pre>' % esc(BIAS)
if not claude_ready: kap_html += '<p class="line">Confronto con la lettura di Claude: non ancora (data/claude_read.json non esiste).</p>'
def termtab(side, col):
    t = LOD[LOD.side == side].sort_values('z', ascending=(side == 'Others')).head(8)
    return table_html(t, ['term', col, 'z'], ['Termine', 'Articoli', 'z'], [None, lambda x: it(x), lambda x: it(abs(x), 1)]) if len(t) else '<p class="line">Dati ancora parziali.</p>'
def wordtab(side):
    t = TW[TW.side == side].sort_values('z', ascending=(side == 'right')).head(8) if len(TW) else TW
    return table_html(t, ['term', 'articles_left' if side == 'left' else 'articles_right', 'z'], ['Parola', 'Titoli', 'z'], [None, lambda x: it(x), lambda x: it(abs(x), 1)]) if len(t) else '<p class="line">Dati ancora parziali (servono almeno 10 titoli per lato).</p>'
FIG = [('c1_ostili_italia_altri', 'Quota di articoli ostili verso i manifestanti: Italia contro altri paesi, su tutta la copertura e sulle sole proteste nel paese della testata. Barra sottile: intervallo al 95%% (ricampionamento delle testate); periodo %s / %s.' % WINDOW, S['c1']),
       ('c2_violenza_richieste', 'Quota media delle frasi di un articolo dedicate alla violenza e alle richieste dei manifestanti, per gruppo di paesi e per vista.', S['c2']),
       ('c3_paesi', 'Quota di articoli ostili verso i manifestanti per paese: una riga per i giornali di un paese, punto e linea con intervallo al 95%% (ricampionamento delle testate), n in grigio; fascia rossa = intervallo dell\'Italia; paesi con meno di %d testi analizzati riuniti in una riga.' % DOT_MIN, S['c3']),
       ('c4_settimane', 'Quota di articoli ostili per settimana, Italia contro altri paesi; settimane dal lunedì, punti solo dove ci sono almeno 20 articoli per gruppo.', S['c4']),
       ('c5_orientamento', 'Quota di articoli ostili per orientamento politico della testata (testate italiane: classificazione di Luca Bagnariol; altri paesi: fonti e disaccordi in data/leaning); barra piena Italia, barra vuota altri paesi.', S['c5'])]
def build_html(images):
    fig = ''
    for k, cap, sent in FIG:
        img = '<img alt="%s" src="data:image/png;base64,%s">' % (esc(cap), b64('%s/charts/%s.png' % (R, k))) if images == 'png' else charts[k]
        fig += '<figure><figcaption>%s</figcaption>%s<p class="line">%s</p></figure>' % (esc(cap), img, esc(sent))
    title = 'Come i giornali raccontano le proteste giovanili: Italia e altri %d paesi, dal %s al %s' % (n_countries, WINDOW[0], WINDOW[1])
    en = ('English summary (generated from the same numbers). %s ' % S['status'].replace('Stato dei dati', 'Data status')) + (
        'Hostile articles toward protesters: Italy %s, others %s (difference %s points, 95%% interval %s to %s; Italy n=%s, others n=%s). ' % (pct(D('all', 'hostile')['italy']), pct(D('all', 'hostile')['others']), pp(D('all', 'hostile')['diff']), pp(D('all', 'hostile')['lo']), pp(D('all', 'hostile')['hi']), it(D('all', 'hostile')['n_italy']), it(D('all', 'hostile')['n_others'])) +
        'The difference is %s. ' % {'più ostili verso i manifestanti degli altri paesi': 'above zero (Italy more hostile)', 'meno ostili verso i manifestanti degli altri paesi': 'below zero (Italy less hostile)', 'dati insufficienti per confrontare': 'not computable yet'}.get(verdict(D('all', 'hostile'), 'più ostili verso i manifestanti degli altri paesi', 'meno ostili verso i manifestanti degli altri paesi', 'x'), 'not distinguishable from zero') +
        'Intervals resample outlets, not articles; labels are model output (Qwen3.8-27B), checked against a second model and a Claude read when available. See Limiti.') if min(D('all', 'hostile')['n_italy'], D('all', 'hostile')['n_others']) >= MINN else 'English summary: data still partial; ' + S['status']
    return '<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title><style>%s</style></head><body><main>' % (esc(title), CSS) + \
        '<div class="logo">Para<i>//</i>asse</div><h1>%s</h1>' % esc(title) + \
        '<div class="answer"><p>%s</p><p>%s</p><p>%s</p></div>' % (esc(S['h1']), esc(S['h2']), esc(S['caveat'])) + '<p class="status">%s</p>' % esc(S['status']) + fig + \
        '<h2>Le parole</h2><p class="line">Termini delegittimanti copiati dagli articoli (log-odds con prior informativo calcolato su tutti gli articoli, Monroe et al. 2008; articoli italiani contro gli altri; le lingue sono diverse, quindi i termini italiani risaltano per costruzione).</p><div style="display:grid;grid-template-columns:1fr 1fr;gap:16px"><div><b>Italia</b>%s</div><div><b>Altri paesi</b>%s</div></div>' % (termtab('Italy', 'articles_italy'), termtab('Others', 'articles_others')) + \
        '<p class="line">Parole dei titoli italiani, testate di sinistra e centro-sinistra contro destra e centro-destra (solo titoli in italiano; %s titoli scartati; %s titoli a sinistra, %s a destra).</p><div style="display:grid;grid-template-columns:1fr 1fr;gap:16px"><div><b>Sinistra</b>%s</div><div><b>Destra</b>%s</div></div>' % (it(n_title_dropped), it(len(left)), it(len(right)), wordtab('left'), wordtab('right')) + \
        '<div class="box"><h2>Metodo</h2><ul>%s</ul><h2 style="margin-top:.8em">Accordo tra modelli</h2>%s</div>' % (''.join(methods), kap_html) + \
        '<div class="box"><h2>Limiti</h2><ul>%s</ul></div>' % ''.join('<li>%s</li>' % esc(x) for x in lim) + \
        '<h2>Summary</h2><p class="en">%s</p></main></body></html>' % esc(en)
atomic(R + '/index.html', build_html('svg'))
import weasyprint
tmp = R + '/pdf.tmp.pdf'; weasyprint.HTML(string=build_html('png'), base_url=R).write_pdf(tmp); os.replace(tmp, R + '/parallasse_protests_report.pdf')
zp = R + '/charts.zip.tmp'
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(glob.glob(R + '/charts/*.png') + glob.glob(R + '/charts/*.svg')): z.write(f, 'charts/' + os.path.basename(f))
    for f in sorted(glob.glob(R + '/csv/*.csv')): z.write(f, 'csv/' + os.path.basename(f))
os.replace(zp, R + '/charts.zip')

# ---------- console summary ----------
print('articles labelled:', len(df), '| Italy', n_it_art, 'Others', n_ot_art, '| head', int(df.has_head.sum()), 'body', int(df.has_body.sum()), 'body analysed', int(df.body_ok.sum()), '| domestic body', int((df.body_ok & (df.domestic == True)).sum()))
print('outlets', len(outlets_A), '(Italy %d) | leaning unmatched %d | no meta %d' % (len(it_out), len(unmatched), int((~df.has_meta).sum())))
print('A rows %d (parsed head %d body %d, unparseable %d, errors %d, cut %d) | B rows %d' % (len(rowsA), statsA[('head', 'ok')], statsA[('body', 'ok')], sum(statsA[(k, 'unparseable')] for k in ('head', 'body')), sum(statsA[(k, 'error')] for k in ('head', 'body')), cutA, len(rowsB)))
print(S['h1']); print(S['h2'])
print('wrote', sorted(os.path.basename(p) for p in glob.glob(R + '/*') if os.path.isfile(p)))
