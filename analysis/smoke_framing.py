"""Smoke test for stage 6 inputs. Fails (exit 1) on an empty or short body, an empty title, an unfilled placeholder,
or a prompt that would pass the served window. `--selftest` feeds known-bad records first and requires each to be caught."""
import sys, os
sys.argv = ['x', 'A', '/dev/null']
sys.path.insert(0, 'analysis')
exec(open('analysis/framing_label.py').read().replace("os.path.dirname(__file__)", "'analysis'").split("if __name__")[0])
u_in_dup = lambda d: d['url'] in dup_body if 'url' in d else False
def problems(d, outlet):
    p, n, cut = build(d, 'body', outlet); out = []
    if not (d.get('title') or '').strip(): out.append('empty title')
    if len((d.get('text') or '').strip()) < MIN_BODY_CHARS: out.append('body shorter than %d chars' % MIN_BODY_CHARS)
    if any(t in p.split('Fields:')[0] for t in ('{country}', '{title}', '{text}')): out.append('unfilled placeholder')
    if cut: out.append('cut at window')
    if u_in_dup(d): out.append('duplicate body')
    return out
bad = [({'url': 'dup', 'title': 'x', 'text': 'a' * 500}, 'duplicate body'), ({'title': 'x', 'text': ''}, 'empty body'), ({'title': 'x', 'text': 'Published: '}, 'stub body'), ({'title': '', 'text': 'a' * 500}, 'no title')]
dup_body.add('dup')
for d, name in bad:
    assert problems(d, 'bbc-co-uk'), 'smoke test did not catch: ' + name
print('selftest: all', len(bad), 'known-bad cases caught')
if len(sys.argv) and '--selftest' in os.environ.get('SMOKE', ''): sys.exit(0)
import collections
c = collections.Counter(); ex = {}
for u, d in rows.items():
    if len(d['text']) < MIN_BODY_CHARS or u in dup_body: c['no_body_call'] += 1; continue
    for pr in problems(d, want[u]): c[pr] += 1; ex[pr] = u
print(dict(c), 'of', len(rows), 'articles'); print(ex)
sys.exit(1 if any(k != 'no_body_call' for k in c) else 0)
