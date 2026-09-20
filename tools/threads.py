#!/usr/bin/env python3
"""threads — get issue/PR threads through the GitHub REST API and read them offline.

NEVER scrape HTML for this (the scraped page holds only the first ~15 comments; an API call returns the complete list).
The token is read from the GH_TOKEN environment variable and is never written anywhere.

  threads.py list      --corpus z1 [--out data/issues-list.json]     # every issue+PR of the repo: number, title, state, dates, comment count
  threads.py fullfetch --corpus z1 N [N ...]                          # cache complete threads under .cache/full[-z2]/N.json (resumable)
  threads.py readfull  --corpus z1 [--maint-only] [--min 60] [--cap 700] [--q 400] [--users 0] N [N ...]

Corpus z1 = project.json "primary" repo, z2 = "secondary". Maintainer logins come from project.json "maintainers" (default: the owner).
A single shell command is limited to ~300 s in the working environment: fetch in chunks (the cache makes reruns free).
"""
import signal
if hasattr(signal, 'SIGPIPE'): signal.signal(signal.SIGPIPE, signal.SIG_DFL)   # allow `| head` without a traceback
import argparse, json, os, sys, time, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def project():
    p = os.path.join(ROOT, 'project.json')
    if not os.path.exists(p):
        sys.exit('project.json missing: {"owner": "...", "primary": "repo", "secondary": "repo2", "maintainers": ["login"]}')
    return json.load(open(p, encoding='utf-8'))


def repo_of(corpus):
    pr = project()
    return pr['owner'], (pr['primary'] if corpus == 'z1' else pr['secondary'])


def maintainers():
    pr = project()
    return set(pr.get('maintainers') or [pr['owner']])


def api(url):
    h = {'Accept': 'application/vnd.github+json', 'User-Agent': 'prior-art-playbook'}
    tok = os.environ.get('GH_TOKEN')
    if tok:
        h['Authorization'] = 'Bearer ' + tok
    with urllib.request.urlopen(urllib.request.Request(url, headers=h)) as r:
        return json.load(r), r.headers.get('Link', '')


def cache_dir(corpus):
    d = os.path.join(ROOT, '.cache', 'full' if corpus == 'z1' else 'full-z2')
    os.makedirs(d, exist_ok=True)
    return d


def cmd_list(a):
    owner, repo = repo_of(a.corpus)
    items, page = [], 1
    while True:
        b, link = api('https://api.github.com/repos/%s/%s/issues?state=all&per_page=100&page=%d&sort=created&direction=asc' % (owner, repo, page))
        items += b
        if 'rel="next"' not in link:
            break
        page += 1
    out = [{'n': i['number'], 'title': i['title'], 'state': i['state'].upper(), 'reason': (i.get('state_reason') or '').upper() or None,
            'created': i['created_at'][:10], 'closed': (i.get('closed_at') or '')[:10], 'author': (i.get('user') or {}).get('login'),
            'comments': i['comments'], 'pr': 'pull_request' in i, 'merged': bool('pull_request' in i and i['pull_request'].get('merged_at')),
            'labels': [x['name'] for x in i.get('labels', [])]} for i in items]
    out.sort(key=lambda x: x['n'])
    path = a.out or os.path.join(ROOT, 'data', 'issues-list.json' if a.corpus == 'z1' else 'issues-list-z2.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
    print('%d items (%d PRs) -> %s' % (len(out), sum(1 for x in out if x['pr']), path))


def fetch_full(n, corpus):
    p = os.path.join(cache_dir(corpus), '%d.json' % n)
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    owner, repo = repo_of(corpus)
    base = 'https://api.github.com/repos/%s/%s/issues/%d' % (owner, repo, n)
    iss, _ = api(base)
    out = {'n': n, 'title': iss['title'], 'author': (iss.get('user') or {}).get('login'), 'created': iss['created_at'][:10],
           'body': iss.get('body') or '', 'ncomments': iss['comments'], 'comments': []}
    page = 1
    while True:
        cs, link = api(base + '/comments?per_page=100&page=%d' % page)
        out['comments'] += [{'a': (c.get('user') or {}).get('login'), 't': c.get('body') or '', 'd': c['created_at'][:10]} for c in cs]
        if 'rel="next"' not in link:
            break
        page += 1
    json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    return out


def cmd_fullfetch(a):
    ok = 0
    for n in a.nums:
        try:
            fetch_full(n, a.corpus)
            ok += 1
        except Exception as e:  # keep going: the cache makes a rerun cheap
            print('fail', n, e)
        time.sleep(0.05)
    print('fetched %d of %d' % (ok, len(a.nums)))


def cmd_readfull(a):
    m = maintainers()
    for n in a.nums:
        o = fetch_full(n, a.corpus)
        print('=== #%d [%s] %s  (comments %d)' % (n, o['created'], o['title'][:90], o['ncomments']))
        if not a.maint_only:
            print('Q: %s' % o['body'][:a.q].strip().replace('\r', ''))
        for c in o['comments']:
            t = c['t'].strip().replace('\r', '')
            if c['a'] in m:
                if len(t) < a.min:
                    continue
                print('M[%s]: %s' % (c['d'], t[:a.cap] + (' [..cut]' if len(t) > a.cap else '')))
            elif a.users:
                print('u: %s' % t[:a.users])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('list'); s.add_argument('--corpus', default='z1', choices=['z1', 'z2']); s.add_argument('--out'); s.set_defaults(f=cmd_list)
    s = sp.add_parser('fullfetch'); s.add_argument('--corpus', default='z1', choices=['z1', 'z2']); s.add_argument('nums', type=int, nargs='+'); s.set_defaults(f=cmd_fullfetch)
    s = sp.add_parser('readfull'); s.add_argument('--corpus', default='z1', choices=['z1', 'z2']); s.add_argument('nums', type=int, nargs='+')
    s.add_argument('--maint-only', action='store_true'); s.add_argument('--min', type=int, default=0); s.add_argument('--cap', type=int, default=100000)
    s.add_argument('--q', type=int, default=400); s.add_argument('--users', type=int, default=0); s.set_defaults(f=cmd_readfull)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
