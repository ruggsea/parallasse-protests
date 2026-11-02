"""Compare the constants block in PLAN.md with analysis/constants.py and with the data. Exit 1 on any mismatch."""
import re, sys, json, glob
sys.path.insert(0, 'analysis')
import constants as C
opn = C.opn
plan = dict(re.findall(r'^(\w+) = (.+)$', re.search(r'```\n(.*?)```', open('PLAN.md').read(), re.S).group(1), re.M))
expect = {'WINDOW': '%s .. %s' % C.WINDOW, 'GATE1_CHARS': C.GATE1_CHARS, 'LABEL_CHARS': C.LABEL_CHARS, 'PAYWALL_MIN_CHARS': C.PAYWALL_MIN_CHARS,
  'SERVED_WINDOW': C.SERVED_WINDOW, 'MAX_TOKENS_A': C.MAX_TOKENS['A'], 'MAX_TOKENS_B': C.MAX_TOKENS['B'], 'TEMPERATURE': C.TEMPERATURE,
  'MIN_BODY_CHARS': C.MIN_BODY_CHARS, 'LIVE_BLOG_CHARS': C.LIVE_BLOG_CHARS, 'CLAUDE_SAMPLE_ITALIAN': C.CLAUDE_SAMPLE['italian'],
  'CLAUDE_SAMPLE_OTHER': C.CLAUDE_SAMPLE['other'], 'CLAUDE_SAMPLE_SEED': C.CLAUDE_SAMPLE['seed'], 'KAPPA_SAMPLE_ITALIAN': C.KAPPA_SAMPLE['italian'],
  'KAPPA_SAMPLE_OTHER': C.KAPPA_SAMPLE['other'], 'KAPPA_SAMPLE_SEED': C.KAPPA_SAMPLE['seed'], 'DUP_HEAD_CHARS': C.DUP_HEAD_CHARS}
bad = [k for k in set(plan) | set(expect) if k in expect and str(expect[k]) != plan.get(k) or k not in expect and k not in ('RELEVANCE_ROWS_GATE1', 'RELEVANCE_ROWS_GATE2', 'FRAMING_ARTICLES')]
# constants as written in the scripts that apply them
code = open('analysis/prefilter.py').read() + open('analysis/relevance_label.py').read() + open('scrapers/mark_paywall.py').read()
for pat, val, name in [(r'\[:1500\]', None, 'LABEL_CHARS/GATE1_CHARS 1500 literal'), (r'< 1500', None, 'PAYWALL_MIN_CHARS 1500 literal')]:
    if not re.search(pat, code): bad.append('code no longer contains ' + name)
data = {'RELEVANCE_ROWS_GATE1': len({json.loads(l)['url'] for l in opn('data/relevance_qwen.jsonl')}),
        'RELEVANCE_ROWS_GATE2': len({json.loads(l)['url'] for l in open('data/relevance_qwen2.jsonl')})}
skipped = []
if glob.glob('data/articles/*.jsonl'):
    sys.argv = ['x', 'A', '/dev/null']
    exec(open('analysis/framing_label.py').read().replace("os.path.dirname(__file__)", "'analysis'").split("if __name__")[0])
    data['FRAMING_ARTICLES'] = len(rows)
else:
    skipped.append('FRAMING_ARTICLES (needs data/articles, article text is not shipped)')
for k, v in data.items():
    if str(v) != plan[k]: bad.append('%s: PLAN %s, data %s' % (k, plan[k], v))
print('mismatches:', bad); print('NOT CHECKED:', skipped)
sys.exit(1 if bad else 0)
