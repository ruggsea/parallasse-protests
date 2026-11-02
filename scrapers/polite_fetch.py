#!/usr/bin/env python3
"""Polite fetcher: robots.txt first, per-host rate limit, every request logged, body cached.
CLI: polite_fetch.py URL [--head N]   prints the body (first N chars) to stdout; exit 2 = robots disallow, 3 = http/network error.
Library: from polite_fetch import fetch -> (status, body|None, robots_path)
Robots: answers and allows -> go; disallows -> refuse (never overridden); unreachable/5xx/4xx-not-429 -> proceed (Ruggero 2026-09-25), recorded as 'assumed_open'.
Rate: 1 req/s per host start, +1 per 5 min while no 429/503 and latency < 1.5x first, cap 8 for big hosts, 2 for others (BIG list); halve and hold 30 min on 429/503.
"""
import hashlib, json, os, sys, time, urllib.parse, urllib.request, urllib.robotparser, fcntl
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs/fetch.log"
CACHE = ROOT / "data/fetchcache"
ROBOTS_LOG = ROOT / "data/robots_paths.tsv"
UA = "ParallasseResearchBot/1.0 (+data-journalism study; contact rmlazza@gmail.com)"
STATE = ROOT / "logs/host_state"
BIG = ("archive.org", "wikipedia.org", "gdeltproject.org", "reuters.com", "bbc.co.uk", "bbc.com", "theguardian.com", "lemonde.fr", "repubblica.it", "corriere.it")
_robots = {}

def _host_state(host):
    STATE.mkdir(parents=True, exist_ok=True)
    return STATE / (host + ".json")

def _wait(host):
    p = _host_state(host)
    cap = 8 if host.endswith(BIG) else 2
    p.touch(exist_ok=True)
    with open(p, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            s = json.loads(f.read() or "{}")
        except ValueError:
            s = {}
        now = time.time()
        s.setdefault("rate", 1.0); s.setdefault("since", now); s.setdefault("last", 0); s.setdefault("hold_until", 0)
        if now >= s["hold_until"] and now - s["since"] > 300 and s["rate"] < cap:
            s["rate"] = min(cap, s["rate"] + 1); s["since"] = now
        sleep = max(0, s["last"] + 1.0 / s["rate"] - now)
        s["last"] = now + sleep
        f.seek(0); f.truncate(); f.write(json.dumps(s))
    time.sleep(sleep)

def _penalise(host):
    p = _host_state(host)
    with open(p, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        s = json.loads(f.read() or "{}")
        s["rate"] = max(0.25, s.get("rate", 1.0) / 2); s["hold_until"] = time.time() + 1800; s["since"] = time.time()
        f.seek(0); f.truncate(); f.write(json.dumps(s))

def _log(url, status, note=""):
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\t{status}\t{url}\t{note}\n")

def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,it,fr,de,es;q=0.8"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(80_000_000), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, b"", time.time() - t
    except Exception as e:
        return 0, str(e).encode(), time.time() - t

def robots_for(host, scheme):
    if host in _robots:
        return _robots[host]
    _wait(host)
    status, body, _ = _get(f"{scheme}://{host}/robots.txt", 15)
    _log(f"{scheme}://{host}/robots.txt", status, "robots")
    rp = urllib.robotparser.RobotFileParser()
    if status == 200:
        rp.parse(body.decode("utf-8", "replace").splitlines()); path = "fetched"
    elif status == 429:
        rp = None; path = "backoff"
    else:
        rp = None; path = "assumed_open"
    _robots[host] = (rp, path)
    ROBOTS_LOG.parent.mkdir(exist_ok=True)
    with open(ROBOTS_LOG, "a") as f:
        f.write(f"{host}\t{path}\t{status}\n")
    return _robots[host]

def fetch(url, cache=True):
    u = urllib.parse.urlparse(url)
    rp, path = robots_for(u.netloc, u.scheme)
    if path == "backoff":
        _penalise(u.netloc); _log(url, "robots429", "backoff"); return 429, None, path
    if rp is not None and not (rp.can_fetch(UA, url)):
        _log(url, "robots_disallow", path); return -1, None, path
    key = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")
    _wait(u.netloc)
    status, body, lat = _get(url)
    _log(url, status, f"{path} lat={lat:.2f}")
    if status in (429, 503):
        _penalise(u.netloc)
    if body[:2] == b"\x1f\x8b":
        import gzip; body = gzip.decompress(body)
    text = body.decode("utf-8", "replace") if status == 200 else None
    if cache:
        CACHE.mkdir(parents=True, exist_ok=True)
        key.write_text(json.dumps({"url": url, "status": status, "robots": path, "text": text}))
    return status, text, path

if __name__ == "__main__":
    url = sys.argv[1]
    head = int(sys.argv[sys.argv.index("--head") + 1]) if "--head" in sys.argv else 60000
    status, text, path = fetch(url)
    if status == -1:
        print("REFUSED: robots.txt disallows this URL", file=sys.stderr); sys.exit(2)
    if status != 200:
        print(f"HTTP {status}", file=sys.stderr); sys.exit(3)
    import re, html as _h
    if "--raw" not in sys.argv:
        text = re.sub(r"(?is)<(script|style|noscript|svg)\\b.*?</\\1>", " ", text)
        text = re.sub(r"(?s)<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", lambda m: f"{m.group(2)} <{m.group(1)}>", text)
        text = _h.unescape(re.sub(r"<[^>]+>", " ", text)); text = re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text))
    print(text[:head])
