"""Write the Claude-read sample in 6 blind chunks (title + cleaned text, no model labels) to tmp/read_D{0..5}.json and the key to tmp/key_D.json."""
import sys, json
sys.argv = ['x', 'A', '/dev/null']; sys.path.insert(0, 'analysis')
exec(open('analysis/framing_label.py').read().replace("os.path.dirname(__file__)", "'analysis'").split("if __name__")[0])
urls = open('data/claude_sample_urls.txt').read().split()
import random; random.Random(7).shuffle(urls)
items = [{'id': 'D%03d' % i, 'country_of_outlet': country.get(want[u]), 'title': rows[u]['title'], 'text': rows[u]['text'][:12000]} for i, u in enumerate(urls)]
json.dump({'D%03d' % i: {'url': u, 'outlet': want[u]} for i, u in enumerate(urls)}, open('tmp/key_D.json', 'w'))
for c in range(6): json.dump(items[c * 50:(c + 1) * 50], open('tmp/read_D%d.json' % c, 'w'), ensure_ascii=False)
print(len(items), sum(len(i['text']) for i in items))
