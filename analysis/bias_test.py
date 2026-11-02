"""Bias test of the body prompt (2026-10-30). Prints hostile rates and agreement for the original labels and each arm,
Italy and others apart, with n and a 95% interval from resampling outlets; and A against the Claude read split Italy / others."""
import json, re, csv, collections, numpy as np
from sklearn.metrics import cohen_kappa_score
import sys; sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from constants import opn
R = str(__import__("pathlib").Path(__file__).resolve().parents[1]) + '/'
country = {r['id']: r['country'] for r in csv.DictReader(open(R + 'data/ledger.tsv'), delimiter='\t')}
def load(p, kind='body'):
    out = {}
    for l in opn(R + p):
        r = json.loads(l)
        if r['kind'] != kind or not r['raw'] or r['raw'].startswith('ERR'): continue
        m = re.search(r'\{.*\}', r['raw'], re.S)
        try: j = json.loads(m.group(0))
        except Exception: continue
        out[r['url']] = (r['outlet'], j.get('stance_protesters'))
    return out
orig = load('data/framing_A.jsonl'); arms = {'senza riga paese': load('data/framing_A_nocountry.jsonl'), 'paese scambiato': load('data/framing_A_swap.jsonl')}
rng = np.random.default_rng(20261030)
def rate(pairs):  # pairs: (outlet, hostile 0/1) -> est, lo, hi (outlet resampling)
    by = collections.defaultdict(list)
    for o, h in pairs: by[o].append(h)
    ks = list(by); N = np.array([sum(by[k]) for k in ks]); D = np.array([len(by[k]) for k in ks]); est = N.sum() / D.sum()
    idx = rng.integers(0, len(ks), (2000, len(ks))); r = N[idx].sum(1) / D[idx].sum(1); return est, np.percentile(r, 2.5), np.percentile(r, 97.5), int(D.sum()), len(ks)
def diffci(pa, pb):  # difference of rates a-b, resampling outlets in each group
    def mats(p):
        by = collections.defaultdict(list)
        for o, h in p: by[o].append(h)
        ks = list(by); return np.array([sum(by[k]) for k in ks]), np.array([len(by[k]) for k in ks])
    (Na, Da), (Nb, Db) = mats(pa), mats(pb); est = Na.sum() / Da.sum() - Nb.sum() / Db.sum()
    ia = rng.integers(0, len(Na), (2000, len(Na))); ib = rng.integers(0, len(Nb), (2000, len(Nb)))
    d = Na[ia].sum(1) / Da[ia].sum(1) - Nb[ib].sum(1) / Db[ib].sum(1); return est, np.percentile(d, 2.5), np.percentile(d, 97.5)
f = lambda x: '%.1f%%' % (100 * x)
fp = lambda x: '%+.1f' % (100 * x)
res = {}
for name, arm in arms.items():
    common = [u for u in arm if u in orig and arm[u][1] in ('supportive', 'neutral', 'hostile') and orig[u][1] in ('supportive', 'neutral', 'hostile')]
    print('\n== %s: %d articles with both labels' % (name, len(common)))
    for grp, test in (('Italia', lambda o: country.get(o) == 'Italy'), ('altri paesi', lambda o: country.get(o) != 'Italy')):
        us = [u for u in common if test(orig[u][0])]
        po = [(orig[u][0], int(orig[u][1] == 'hostile')) for u in us]; pa = [(arm[u][0], int(arm[u][1] == 'hostile')) for u in us]
        eo, lo, hi, n, k = rate(po); ea, lo2, hi2, _, _ = rate(pa)
        dif = [x - y for x, y in zip([p[1] for p in pa], [p[1] for p in po])]
        _, dl, dh = diffci(pa, po) if False else (0, np.percentile([np.mean(rng.choice(dif, len(dif))) for _ in range(2000)], 2.5), np.percentile([np.mean(rng.choice(dif, len(dif))) for _ in range(2000)], 97.5))
        agree = np.mean([orig[u][1] == arm[u][1] for u in us]); kap = cohen_kappa_score([orig[u][1] for u in us], [arm[u][1] for u in us])
        print('%-12s n=%d (%d outlets) | ostili originale %s [%s, %s] | ostili %s: %s [%s, %s] | cambio %s punti (intervallo sugli articoli appaiati %s, %s) | accordo %s kappa %.2f' % (grp, n, k, f(eo), f(lo), f(hi), name, f(ea), f(lo2), f(hi2), fp(ea - eo), fp(dl), fp(dh), f(agree), kap))
    # Italy minus others gap, original vs arm
    for lab, src in (('originale', lambda u: orig[u]), (name, lambda u: arm[u])):
        pi = [(src(u)[0], int(src(u)[1] == 'hostile')) for u in common if country.get(orig[u][0]) == 'Italy']; po_ = [(src(u)[0], int(src(u)[1] == 'hostile')) for u in common if country.get(orig[u][0]) != 'Italy']
        e, lo, hi = diffci(pi, po_); print('  scarto Italia meno altri (%s): %s punti [%s, %s]' % (lab, fp(e), fp(lo), fp(hi)))
# Claude read split
cl = json.load(open(R + 'data/claude_read.json'))
print('\n== modello A (prompt originale) contro lettura di Claude, stance_protesters')
for grp, test in (('Italia', lambda o: country.get(o) == 'Italy'), ('altri paesi', lambda o: country.get(o) != 'Italy')):
    us = [u for u in cl if u in orig and test(orig[u][0]) and cl[u].get('stance_protesters') in ('supportive', 'neutral', 'hostile') and orig[u][1] in ('supportive', 'neutral', 'hostile')]
    a = [orig[u][1] for u in us]; c = [cl[u]['stance_protesters'] for u in us]
    ha = np.array([x == 'hostile' for x in a]); hc = np.array([x == 'hostile' for x in c])
    print('%-12s n=%d | accordo %s kappa %.2f | ostili: modello %s, Claude %s | modello ostile e Claude no: %d, Claude ostile e modello no: %d' % (grp, len(us), f(np.mean([x == y for x, y in zip(a, c)])), cohen_kappa_score(a, c), f(ha.mean()), f(hc.mean()), int((ha & ~hc).sum()), int((~ha & hc).sum())))
