"""Draw the kappa sample (300 Italian + 300 other articles that get a body call) and the Claude-read sample
(first 200 Italian and first 100 other of the same shuffled lists), so models A, B and the Claude read all label the same articles.
Writes data/kappa_urls.txt and data/claude_sample_urls.txt."""
import sys, random
sys.argv = ['x', 'A', '/dev/null']; sys.path.insert(0, 'analysis')
exec(open('analysis/framing_label.py').read().replace("os.path.dirname(__file__)", "'analysis'").split("if __name__")[0])
rng = random.Random(KAPPA_SAMPLE['seed'])
pool = sorted(u for u, d in rows.items() if len(d['text']) >= MIN_BODY_CHARS and u not in dup_body and len(d['text']) < LIVE_BLOG_CHARS)
it = [u for u in pool if country.get(want[u]) == 'Italy']; ot = [u for u in pool if country.get(want[u]) != 'Italy']
rng.shuffle(it); rng.shuffle(ot)
k = it[:KAPPA_SAMPLE['italian']] + ot[:KAPPA_SAMPLE['other']]
c = it[:CLAUDE_SAMPLE['italian']] + ot[:CLAUDE_SAMPLE['other']]
open('data/kappa_urls.txt', 'w').write('\n'.join(k)); open('data/claude_sample_urls.txt', 'w').write('\n'.join(c))
print(len(pool), len(it), len(ot), len(k), len(c))
