"""Hand-read validation sample per the pre-registration: >=200 Italian + >=100 other.
Deterministic (fixed seed). Writes data/validation_sample.tsv + .jsonl.
"""
import json, random, sys
root = str(__import__("pathlib").Path(__file__).resolve().parents[1])
n_it = int(sys.argv[1]) if len(sys.argv) > 1 else 200
n_other = int(sys.argv[2]) if len(sys.argv) > 2 else 100
country = {}
for line in open(root + '/data/ledger.tsv'):
    p = line.rstrip('\n').split('\t')
    if len(p) >= 2 and p[0] != 'id': country[p[0]] = p[1]
rows = []
for line in open(root + '/data/framing_qwen.jsonl'):
    o = json.loads(line); r = o.get('raw', '')
    if r.startswith('ERR'): continue
    try: d = json.loads(r)
    except Exception: continue
    rows.append((o['outlet'], o['url'], d))
it = [t for t in rows if country.get(t[0]) == 'Italy']
ot = [t for t in rows if country.get(t[0]) != 'Italy']
rnd = random.Random(20261029); rnd.shuffle(it); rnd.shuffle(ot)
seen = {}; pick = []
for t in it:
    if seen.get(t[0], 0) < 3: seen[t[0]] = seen.get(t[0], 0) + 1; pick.append(t)
    if len(pick) >= n_it: break
for t in it:
    if len(pick) >= n_it: break
    if t not in pick: pick.append(t)
pick += ot[:n_other]
cols = ['stance_protesters','protest_type','region','share_violence_sentences','share_demands_sentences','quoted','labels_delegitimising','labels_counterpart']
w = open(root + '/data/validation_sample.tsv', 'w')
w.write('\t'.join(['outlet','country','url','hand_stance','hand_type','hand_region','hand_violence','hand_demands','note'] + ['model_'+c for c in cols]) + '\n')
with open(root + '/data/validation_sample.jsonl', 'w') as f:
    for o, u, d in pick:
        f.write(json.dumps({'outlet': o, 'country': country.get(o,'?'), 'url': u, 'model': d}) + '\n')
        w.write('\t'.join([o, country.get(o,'?'), u, '', '', '', '', '', ''] + [json.dumps(d.get(c)) for c in cols]) + '\n')
w.close()
print('picked', len(pick), 'italian', sum(1 for t in pick if country.get(t[0])=='Italy'), 'other', sum(1 for t in pick if country.get(t[0])!='Italy'))
