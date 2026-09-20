#!/usr/bin/env python3
"""pz — atomised, resumable triage of a project's issues and commits (reference implementation of the prior-art-playbook).

Source of truth = the record files in records/. STATE.json and indexes/ are derived.
Stdlib only (Python >= 3.8). Run `python tools/pz.py --help`.

Record = markdown file with a JSON-valued frontmatter (valid YAML) + '## Summary' + '## Notes'.
Status ladder:  stub -> triaged (heuristic tags) -> read (a human/LLM read the source text)
                -> analyzed (manual tags + summary + class links).

Refs: i<issue number>, c<commit hash prefix>; for the secondary corpus prefix with z2 (z2i75, z2c1a2b3c).
Fast tagging (several refs may share a line: i1,i2,c1a2b3c): write one line per record in a batch file, then `pz apply batch.tsv`:

    i1836 | M1,S2 | cause:byte-cutoff layer:probe proto:tls os:any target:cdn outcome:workaround auto:detect+handle conf:stated impact:breaks-target | one-line summary
    c187affb | R2 | ctype:feature engine:nfqws cause:seqovl | summary

  ref      i<issue number> | c<commit hash prefix>
  classes  comma list of class ids (see taxonomy/classes.json) or '-'
  tags     facet:value tokens; a facet mentioned here REPLACES that facet's previous values.
           extra tokens: status=read|analyzed  depth=title|thread|full|source  (default: analyzed, thread for issues / title for commits)
  summary  free text (optional). Replaces the summary; start with '+ ' to APPEND instead.
"""
import signal
if hasattr(signal, 'SIGPIPE'): signal.signal(signal.SIGPIPE, signal.SIG_DFL)   # allow `| head` without a traceback
import argparse, csv, datetime, json, os, re, subprocess, sys, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def project():
    """project.json: {"owner": "...", "primary": "repo", "secondary": "repo2", "maintainers": ["login"]}"""
    p = os.path.join(ROOT, 'project.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {'owner': 'OWNER', 'primary': 'REPO', 'secondary': 'REPO2'}
REC = {'issue': os.path.join(ROOT, 'records', 'issues'), 'commit': os.path.join(ROOT, 'records', 'commits')}   # zapret (z1)
REPOS = ('z1', 'z2')
def rec_dir(repo, kind):
    if repo == 'z1': return REC[kind]
    return os.path.join(ROOT, 'records', 'z2', 'issues' if kind == 'issue' else 'commits')   # zapret2 (z2)
def repo_of(path):
    return 'z2' if (os.sep + 'z2' + os.sep) in path else 'z1'
def refname(fm, k, path):
    pre = 'z2' if repo_of(path) == 'z2' else ''
    return pre + (('i%d' % fm['id']) if k == 'issue' else ('c' + fm['hash']))
def label(fm, k, path):
    pre = 'z2 ' if repo_of(path) == 'z2' else ''
    return pre + (('#%d' % fm['id']) if k == 'issue' else '`%s`' % fm['hash'])
TAX = os.path.join(ROOT, 'taxonomy', 'facets.json')
CLS = os.path.join(ROOT, 'taxonomy', 'classes.json')
for _d in list(REC.values()) + [rec_dir('z2', 'issue'), rec_dir('z2', 'commit'), os.path.join(ROOT, 'indexes'), os.path.join(ROOT, 'batches'), os.path.join(ROOT, 'taxonomy')]:
    os.makedirs(_d, exist_ok=True)   # git does not track empty dirs: a fresh clone must still work
STATUS_ORDER = ['stub', 'triaged', 'read', 'analyzed']
DEPTH_ORDER = ['title', 'thread', 'full', 'source']
FM_ORDER = ['kind', 'repo', 'pr', 'id', 'hash', 'title', 'url', 'date', 'state', 'files', 'adds', 'dels', 'refs',
            'status', 'depth', 'tagged_by', 'classes', 'classes_inferred', 'tags', 'cited_in']


# ---------------------------------------------------------------- io
def load_tax():
    return json.load(open(TAX, encoding='utf-8'))['facets']

def load_classes():
    return json.load(open(CLS, encoding='utf-8')) if os.path.exists(CLS) else {}

def rec_path(kind, rid, h=None, repo='z1'):
    if kind == 'issue':
        return os.path.join(rec_dir(repo, 'issue'), '%04d.md' % int(rid))
    return os.path.join(rec_dir(repo, 'commit'), '%04d-%s.md' % (int(rid), h))

def parse(path):
    txt = open(path, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n(.*)\Z', txt, re.S)
    fm = {}
    for line in m.group(1).split('\n'):
        k, _, v = line.partition(': ')
        fm[k] = json.loads(v)
    body = m.group(2)
    s = re.search(r'## Summary\n(.*?)(?=\n## |\Z)', body, re.S)
    n = re.search(r'## Notes\n(.*)\Z', body, re.S)
    return fm, (s.group(1).strip() if s else ''), (n.group(1).strip() if n else '')

def dump(path, fm, summary, notes):
    keys = [k for k in FM_ORDER if k in fm] + [k for k in fm if k not in FM_ORDER]
    head = '\n'.join('%s: %s' % (k, json.dumps(fm[k], ensure_ascii=False)) for k in keys)
    body = '\n## Summary\n%s\n\n## Notes\n%s\n' % (summary or '_(none yet)_', notes or '')
    tmp = path + '.tmp'
    open(tmp, 'w', encoding='utf-8').write('---\n%s\n---\n%s' % (head, body))
    os.replace(tmp, path)  # atomic per record

def all_records(kind=None, repo=None):
    for r in ([repo] if repo else REPOS):
        for k in ([kind] if kind else ['issue', 'commit']):
            d = rec_dir(r, k)
            if not os.path.isdir(d): continue
            for f in sorted(os.listdir(d)):
                if f.endswith('.md'):
                    yield k, os.path.join(d, f)

def find_commit(prefix, repo='z1'):
    d = rec_dir(repo, 'commit')
    for f in os.listdir(d):
        if f.endswith('.md') and f.split('-', 1)[1].startswith(prefix):
            return os.path.join(d, f)
    return None

def resolve(ref):
    m = re.match(r'^(z2)?([ic])(.+)$', ref)
    if not m: raise ValueError('bad ref %r (use i<num>, c<hash>, z2i<num> or z2c<hash>)' % ref)
    repo = 'z2' if m.group(1) else 'z1'
    if m.group(2) == 'i': p = rec_path('issue', m.group(3), repo=repo)
    else: p = find_commit(m.group(3), repo)
    if not p or not os.path.exists(p):
        raise ValueError('unknown record %r' % ref)
    return p


# ---------------------------------------------------------------- heuristics (labelled tagged_by=heuristic)
ISSUE_RULES = [
    ('meta', r'donat|донат|лиценз|licens|translate|перевод|scam|offtopic|оффтоп|wiki|packag|опакеч|pkgbuild|readme|релиз|releas|^test$|^del$'),
    ('security', r'virus|вирус|троян|trojan|wacatac|mirai|антивир|kaspersky|касперск|defender|майнер|miner'),
    ('crash', r'crash|падает|зависа|виснет|hang|segfault|segmentation|memleak|утечк|течет|sigsys|bad system call|100% cpu|bus error|перезагруж|reboot|bsod|блюскрин'),
    ('discord', r'discord|дискорд|rtc|войс|голос|\bгс\b|ptc|voice'),
    ('youtube', r'youtube|ютуб|ютьюб|googlevideo|видео|video|замедл|throttl|скорост|speed'),
    ('udp', r'quic|udp|http3|http/3|wireguard|stun|dht'),
    ('parser', r'kyber|sni|clienthello|multisplit|seqovl|disorder|hostfakesplit|syndata|fake|фейк|wssize|ipfrag|autottl|desync|дурен'),
    ('search', r'blockcheck|блокчек|стратег|strategy|подбор'),
    ('scope', r'hostlist|ipset|лист|list|автохост|autohost|exclude|исключен|nozapret'),
    ('dns', r'\bdns\b|doh|днс|dnscrypt'),
    ('collateral', r'game|игр|steam|geforce|valorant|whatsapp|viber|telegram|телег|roblox|minecraft|rockstar|razer|vpn|впн|openvpn|pbr|torrent'),
    ('install', r'install|установ|инсталл|build|собир|сборк|компил|compile|бинар|binar|удал|uninstall|не запускается|автозапуск|service|служб'),
]
OS_RULES = [('keenetic', r'keenetic|кинетик'), ('openwrt', r'openwrt|owrt|роутер|router|xiaomi'), ('macos', r'macos|\bmac\b'),
            ('bsd', r'freebsd|openbsd|pfsense|opnsense'), ('android', r'android|magisk'), ('windows', r'windows|винд|win\d|winws|\.bat|батник'),
            ('linux', r'linux|ubuntu|debian|arch\b|fedora|nixos|gentoo')]
TARGET_RULES = [('youtube', r'youtube|ютуб|googlevideo'), ('discord', r'discord|дискорд'), ('telegram', r'telegram|телег|\bтг\b'),
                ('whatsapp', r'whatsapp|viber'), ('games', r'game|игр|steam|roblox|minecraft|rockstar|cod\b|valorant')]

def heur_issue(title):
    t = title.lower(); tags = []
    hit = [c for c, rx in ISSUE_RULES if re.search(rx, t)]
    m = {'meta': ['kind:meta'], 'security': ['kind:security-report', 'cause:av-flag', 'layer:dist'], 'crash': ['impact:crash'],
         'discord': ['target:discord', 'layer:udp-app'], 'youtube': ['target:youtube'], 'udp': ['proto:udp', 'layer:udp-app'],
         'parser': ['layer:parser'], 'search': ['engine:blockcheck', 'layer:search'], 'scope': ['layer:scope'], 'dns': ['proto:dns'],
         'collateral': ['impact:breaks-nontarget'], 'install': ['kind:support-install', 'layer:ops']}
    for c in hit[:2]: tags += m[c]
    kinds = [t for t in tags if t.startswith('kind:')]
    for extra in kinds[1:]: tags.remove(extra)   # kind is single-valued: keep the first
    for o, rx in OS_RULES:
        if re.search(rx, t): tags.append('os:' + o)
    for g, rx in TARGET_RULES:
        if re.search(rx, t) and 'target:' + g not in tags: tags.append('target:' + g)
    return sorted(set(tags)), bool(hit or tags)

def heur_commit(subject, files):
    s = subject.lower(); tags = []
    if re.match(r'^(merge)', s): tags.append('ctype:maintenance')
    elif re.search(r'^revert', s): tags.append('ctype:revert')
    elif re.search(r'\bfix|bug|crash|leak|regression|broken|oob|uninit|dangling|typo', s): tags.append('ctype:fix')
    elif re.match(r'^(docs?|readme|quick_start|update docs|work on|doc works|docs works)', s) or files and all(f.startswith('docs/') or f.endswith('.md') for f in files):
        tags.append('ctype:docs')
    elif re.search(r'bins?\b|github|makefile|compile|build|upx|binaries|release', s): tags.append('ctype:build')
    elif re.search(r'update (changes|readme)|changes\.txt', s): tags.append('ctype:release')
    elif re.search(r'^(nfqws|tpws|winws|dvtws|blockcheck|init|ipset|mdig)', s): tags.append('ctype:feature')
    else: tags.append('ctype:maintenance')
    eng = set()
    for f in files:
        for pre, e in (('nfq/', 'nfqws'), ('nfq2/', 'nfqws2'), ('lua/', 'lua'), ('blockcheck2', 'blockcheck'), ('tpws/', 'tpws'), ('blockcheck', 'blockcheck'), ('init.d/', 'init'), ('ipset/', 'ipset'), ('mdig/', 'mdig'),
                       ('ip2net/', 'ip2net'), ('docs/', 'docs'), ('.github/', 'ci'), ('install', 'installer'), ('uninstall', 'installer'), ('common/', 'init')):
            if f.startswith(pre): eng.add(e)
    for e in re.findall(r'^(nfqws|tpws|winws|dvtws|blockcheck|ipset|mdig)', s): eng.add(e)
    if 'winws' in s or any('win' in f.lower() and 'binaries' not in f for f in files[:50] if f.startswith('binaries/win')): eng.add('winws')
    tags += ['engine:' + e for e in sorted(eng)]
    if 'winws' in eng: tags.append('os:windows')
    if 'dvtws' in eng: tags.append('os:bsd')
    return tags


# ---------------------------------------------------------------- tag handling
def split_tags(tokens, tax):
    """tokens: list of 'facet:value' -> dict facet->list, raising on bad vocabulary."""
    out = collections.OrderedDict(); errs = []
    for tok in tokens:
        if ':' not in tok: errs.append('bad tag %r' % tok); continue
        f, v = tok.split(':', 1)
        if f not in tax: errs.append('unknown facet %r in %r' % (f, tok)); continue
        if v not in tax[f]['values']: errs.append('unknown value %r for facet %r' % (v, f)); continue
        out.setdefault(f, [])
        if v not in out[f]: out[f].append(v)
        if not tax[f]['multi'] and len(out[f]) > 1: errs.append('facet %r is single-valued: %s' % (f, out[f]))
    if errs: raise ValueError('; '.join(errs))
    return out

def merge_tags(old, new):
    d = collections.OrderedDict()
    for t in old:
        f, v = t.split(':', 1); d.setdefault(f, []).append(v)
    for f, vs in new.items(): d[f] = vs  # replace facet
    return ['%s:%s' % (f, v) for f in d for v in d[f]]


# ---------------------------------------------------------------- commands
def cmd_bootstrap(a):
    """Create records for ONE corpus (z1 = primary repo, z2 = secondary repo): issues + PRs from an API list file
    (written by `threads.py list`) and commits from a local clone. Idempotent: existing records are never touched."""
    proj = project(); corpus = a.corpus
    name = proj['primary'] if corpus == 'z1' else proj['secondary']
    base = 'https://github.com/%s/%s' % (proj['owner'], name)
    use_h = (a.heuristics == 'zapret')
    items = sorted(json.load(open(a.issues, encoding='utf-8')), key=lambda x: x['n'])
    n_new = 0
    for x in items:
        p = rec_path('issue', x['n'], repo=corpus)
        if os.path.exists(p): continue
        tags, hit = heur_issue(x['title']) if use_h else ([], False)
        if x.get('pr'):
            st = 'pr-merged' if x.get('merged') else ('pr-closed' if x['state'] == 'CLOSED' else 'pr-open')
        else:
            st = ('closed' + ('/' + x['reason'].lower() if x.get('reason') else '')) if x['state'] == 'CLOSED' else 'open'
        fm = {'kind': 'issue', 'pr': bool(x.get('pr')), 'id': x['n'], 'title': x['title'],
              'url': '%s/%s/%d' % (base, 'pull' if x.get('pr') else 'issues', x['n']),
              'date': x['created'], 'state': st, 'status': 'triaged' if hit else 'stub', 'depth': 'title',
              'tagged_by': 'heuristic' if hit else 'none', 'classes': [], 'tags': tags, 'cited_in': []}
        if corpus != 'z1': fm['repo'] = corpus
        dump(p, fm, '', ''); n_new += 1
    log = subprocess.run(['git', '-C', a.clone, 'log', '--reverse', '--numstat', '--date=short', '--format=@@%H|%h|%ad|%s'],
                         capture_output=True, text=True, check=True).stdout
    commits = []; cur = None
    for line in log.split('\n'):
        if line.startswith('@@'):
            H, h, d, sj = line[2:].split('|', 3); cur = {'H': H, 'h': h, 'd': d, 's': sj, 'files': [], 'a': 0, 'r': 0}; commits.append(cur)
        elif line.strip() and cur is not None:
            parts = line.split('\t')
            if len(parts) == 3:
                cur['files'].append(parts[2])
                cur['a'] += int(parts[0]) if parts[0].isdigit() else 0
                cur['r'] += int(parts[1]) if parts[1].isdigit() else 0
    c_new = 0
    for i, c in enumerate(commits, 1):
        p = rec_path('commit', i, c['h'], repo=corpus)
        if os.path.exists(p): continue
        tags = heur_commit(c['s'], c['files']) if use_h else []
        refs = sorted({int(n) for n in re.findall(r'#(\d+)', c['s'])})
        fm = {'kind': 'commit', 'id': i, 'hash': c['h'], 'title': c['s'], 'url': base + '/commit/' + c['H'], 'date': c['d'],
              'files': len(c['files']), 'adds': c['a'], 'dels': c['r'], 'refs': refs,
              'status': 'triaged' if use_h else 'stub', 'depth': 'title', 'tagged_by': 'heuristic' if use_h else 'none',
              'classes': [], 'tags': tags, 'cited_in': []}
        if corpus != 'z1': fm['repo'] = corpus
        dump(p, fm, '', ''); c_new += 1
    print('bootstrap %s: %d new issue/PR records, %d new commit records' % (corpus, n_new, c_new))

def cmd_classes_build(a):
    cls = {}
    for f in sorted(os.listdir(os.path.join(ROOT, 'analysis'))):
        if not f.endswith('.md'): continue
        for m in re.finditer(r'^#{2,3} ([A-Z]\d+) — (.+)$', open(os.path.join(ROOT, 'analysis', f), encoding='utf-8').read(), re.M):
            cls[m.group(1)] = {'title': m.group(2).strip(), 'doc': 'analysis/' + f}
    json.dump(cls, open(CLS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    print('classes: %d' % len(cls))

def cmd_backfill_docs(a):
    """Set `cited_in` on the records that the analysis documents cite (issue refs #N, z2#N and backticked commit hashes)
    inside an entry section (## X1 - title). Classes are NOT touched here any more: they are data carried by batches."""
    n = 0
    for f in sorted(os.listdir(os.path.join(ROOT, 'analysis'))):
        if not f.endswith('.md'): continue
        txt = open(os.path.join(ROOT, 'analysis', f), encoding='utf-8').read()
        ref = 'analysis/' + f
        cited = set()
        for sec in re.split(r'(?m)^(?=#{2,3} [A-Z]\d+ \u2014 )', txt):
            if not re.match(r'#{2,3} [A-Z]\d+ \u2014 ', sec): continue
            for z2, num in re.findall(r'(?<![\w`])(z2)?#(\d{1,4})\b', sec):
                cited.add(('issue', 'z2' if z2 else 'z1', num))
            for pre, h in re.findall(r'`(z2:)?([0-9a-f]{7})`', sec):
                cited.add(('commit', 'z2' if pre else 'z1', h))
        for kind, repo, key in cited:
            p = rec_path('issue', key, repo=repo) if kind == 'issue' else find_commit(key, repo)
            if not p or not os.path.exists(p): continue
            fm, sm, nt = parse(p)
            if ref not in fm['cited_in']:
                fm['cited_in'] = sorted(fm['cited_in'] + [ref]); dump(p, fm, sm, nt); n += 1
    print('backfill: %d record updates' % n)

def parse_batch(path, tax, classes):
    ops = []; errs = []
    for ln, line in enumerate(open(path, encoding='utf-8'), 1):
        line = line.rstrip('\n')
        if not line.strip() or line.startswith('#'): continue
        cols = [c.strip() for c in line.split('|', 3)]
        if len(cols) < 3:
            errs.append('line %d: need at least ref | classes | tags' % ln); continue
        refs, cl, tg = cols[0], cols[1], cols[2]
        summ = cols[3] if len(cols) > 3 else ''
        for ref in [r.strip() for r in refs.split(',') if r.strip()]:   # several refs may share one line
            try:
                p = resolve(ref)
                extra = {}; tagtoks = []
                for t in tg.split():
                    if '=' in t:
                        k, v = t.split('=', 1); extra[k] = v
                    else:
                        tagtoks.append(t)
                tags = split_tags(tagtoks, tax)
                cids = [] if cl in ('-', '') else [c.strip() for c in cl.split(',')]
                for c in cids:   # a leading ~ marks an INFERRED class (stored in classes_inferred)
                    if c.lstrip('~') not in classes: raise ValueError('unknown class %r' % c)
                if extra.get('status', 'analyzed') not in STATUS_ORDER[2:]: raise ValueError('status must be read|analyzed')
                if extra.get('depth', '') not in ('',) + tuple(DEPTH_ORDER): raise ValueError('bad depth')
                ops.append((ref, p, cids, tags, extra, summ))
            except ValueError as e:
                errs.append('line %d (%s): %s' % (ln, ref, e))
    return ops, errs

def cmd_check(a):
    """Dry run of a batch: report errors (same as apply) and WARNINGS for the mistakes that cost time before:
    overwriting the summary of an analysed record, a facet line that silently drops existing values, duplicate refs."""
    tax = load_tax(); classes = load_classes()
    ops, errs = parse_batch(a.batch, tax, classes)
    warns = []; seen = collections.Counter()
    for ref, p, cids, tags, extra, summ in ops:
        seen[ref] += 1
        fm, s, nt = parse(p)
        if summ and not summ.startswith('+') and fm['status'] == 'analyzed' and s and s != '_(none yet)_':
            warns.append('%s: replaces the existing summary of an analysed record (start the text with "+ " to append)' % ref)
        for f, vs in tags.items():          # tags: facet -> list of values (from split_tags)
            vals = set(vs)
            lost = {t.split(':', 1)[1] for t in fm['tags'] if t.startswith(f + ':')} - vals
            if lost: warns.append('%s: facet %s replaces %s (restate them if they still hold)' % (ref, f, ','.join(sorted(lost))))
    for r, n in seen.items():
        if n > 1: warns.append('%s appears %d times in this batch' % (r, n))
    for e in errs: print('ERROR  ' + e)
    for w in warns: print('WARN   ' + w)
    print('check: %d records, %d errors, %d warnings' % (len(ops), len(errs), len(warns)))
    sys.exit(1 if errs else 0)

def cmd_apply(a):
    tax = load_tax(); classes = load_classes()
    ops, errs = parse_batch(a.batch, tax, classes)
    if errs:
        print('BATCH REJECTED (nothing written):'); [print('  ' + e) for e in errs]; sys.exit(1)
    for ref, p, cids, tags, extra, summ in ops:  # apply only after whole batch validated
        fm, s, nt = parse(p)
        fm['tags'] = merge_tags(fm['tags'], tags)
        human = [c for c in cids if not c.startswith('~')]; infer = [c[1:] for c in cids if c.startswith('~')]
        if human: fm['classes'] = sorted(set(fm['classes']) | set(human))
        inf = (set(fm.get('classes_inferred', [])) | set(infer)) - set(fm['classes'])
        if inf: fm['classes_inferred'] = sorted(inf)
        else: fm.pop('classes_inferred', None)
        st = extra.get('status', 'analyzed')
        if STATUS_ORDER.index(st) > STATUS_ORDER.index(fm['status']): fm['status'] = st
        dp = extra.get('depth') or ('thread' if fm['kind'] == 'issue' else 'title')
        if DEPTH_ORDER.index(dp) > DEPTH_ORDER.index(fm['depth']): fm['depth'] = dp
        fm['tagged_by'] = 'manual'
        if summ.startswith('+'):   # append mode: keep the existing summary, add a clause (idempotent)
            add = summ[1:].strip()
            base = s if s and s != '_(none yet)_' else ''
            if add and add not in base: s = (base + ' ' + add).strip()
        elif summ: s = summ
        dump(p, fm, s, nt)
    dest = os.path.join(ROOT, 'batches')
    if os.path.abspath(os.path.dirname(a.batch)) != os.path.abspath(dest):
        nxt = 1 + max([int(f[:4]) for f in os.listdir(dest) if re.match(r'\d{4}-', f)] or [0])
        name = a.name or os.path.basename(a.batch).rsplit('.', 1)[0]
        target = os.path.join(dest, '%04d-%s.tsv' % (nxt, name))
        open(target, 'w', encoding='utf-8').write(open(a.batch, encoding='utf-8').read())
        print('archived as', os.path.relpath(target, ROOT))
    print('applied %d records' % len(ops))

def cmd_replay(a):
    """Re-apply every archived batch in order (rebuilds manual tags from scratch on fresh bootstrap)."""
    d = os.path.join(ROOT, 'batches')
    for f in sorted(os.listdir(d)):
        if f.endswith('.tsv'):
            a2 = argparse.Namespace(batch=os.path.join(d, f), name=None); cmd_apply(a2)

def cmd_next(a):
    want = set(a.status.split(','))
    n = 0
    for k, p in all_records(a.kind, a.repo):
        fm, s, nt = parse(p)
        if fm['status'] not in want: continue
        if a.after and fm['id'] <= a.after: continue
        print('%s %s | %s | %s | %s' % (refname(fm, k, p), fm['date'], fm['status'],
                                       ' '.join(fm['tags']), fm['title'][:a.width]))
        n += 1
        if n >= a.n: break
    if n == 0: print('(nothing left with status in %s)' % a.status)

def cmd_show(a):
    p = resolve(a.ref); fm, s, nt = parse(p)
    print(open(p, encoding='utf-8').read())

def stats(repo='z1'):
    c = collections.Counter(); byk = collections.defaultdict(collections.Counter)
    cursors = {}
    for k, p in all_records(repo=repo):
        fm, s, nt = parse(p)
        byk[k][fm['status']] += 1; c[(k, fm['depth'])] += 1; c[(k, 'by:' + fm['tagged_by'])] += 1
        if fm['status'] != 'analyzed' and k not in cursors: cursors[k] = fm['id']
    return byk, c, cursors

def cmd_status(a):
    out = {'updated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%MZ'), 'repos': {}}
    for repo in REPOS:
        byk, c, cursors = stats(repo)
        if not sum(sum(v.values()) for v in byk.values()): continue
        ro = {'kinds': {}, 'cursor_first_not_analyzed': cursors}
        for k in ('issue', 'commit'):
            tot = sum(byk[k].values())
            ro['kinds'][k] = {'total': tot, 'by_status': {s: byk[k].get(s, 0) for s in STATUS_ORDER},
                              'by_depth': {d: c[(k, d)] for d in DEPTH_ORDER}, 'tagged_by': {t: c[(k, 'by:' + t)] for t in ('none', 'heuristic', 'manual')}}
            print('%s %-7s total=%-4d %s | depth %s | first-not-analyzed=%s' % (repo, k, tot, dict(ro['kinds'][k]['by_status']),
                  ro['kinds'][k]['by_depth'], cursors.get(k)))
        out['repos'][repo] = ro
        if repo == 'z1': out['kinds'] = ro['kinds']; out['cursor_first_not_analyzed'] = cursors   # backward compatible keys
    if a.write:
        json.dump(out, open(os.path.join(ROOT, 'STATE.json'), 'w'), indent=1); print('wrote STATE.json')

def cmd_stamp(a):
    """Replace the block between <!-- status:begin --> and <!-- status:end --> in a markdown file with COUNTS COMPUTED FROM THE RECORDS,
    so numbers in READMEs and documents cannot go stale (write derived numbers only through this)."""
    txt = open(a.file, encoding='utf-8').read()
    if '<!-- status:begin -->' not in txt or '<!-- status:end -->' not in txt:
        sys.exit('%s has no <!-- status:begin --> ... <!-- status:end --> markers' % a.file)
    L = []
    for repo in REPOS:
        byk, c, cur = stats(repo)
        for k in ('issue', 'commit'):
            tot = sum(byk[k].values())
            if tot: L.append('- %s %ss: %d, analysed %d; depth %s' % (repo, k, tot, byk[k].get('analyzed', 0), ', '.join('%s %d' % (d, c[(k, d)]) for d in DEPTH_ORDER if c[(k, d)])))
    block = '<!-- status:begin -->\n' + '\n'.join(L) + '\n<!-- generated by pz.py stamp %s; do not edit -->\n<!-- status:end -->' % datetime.date.today().isoformat()
    new = re.sub(r'<!-- status:begin -->.*?<!-- status:end -->', lambda m: block, txt, flags=re.S)
    open(a.file, 'w', encoding='utf-8').write(new); print('stamped', a.file)

def cmd_validate(a):
    tax = load_tax(); classes = load_classes(); errs = []
    for k, p in all_records():
        rel = os.path.relpath(p, ROOT)
        try: fm, s, nt = parse(p)
        except Exception as e: errs.append('%s: unparsable (%s)' % (rel, e)); continue
        if fm.get('kind') != k: errs.append('%s: kind mismatch' % rel)
        if fm['status'] not in STATUS_ORDER: errs.append('%s: bad status' % rel)
        if fm['depth'] not in DEPTH_ORDER: errs.append('%s: bad depth' % rel)
        try: split_tags(fm['tags'], tax)
        except ValueError as e: errs.append('%s: %s' % (rel, e))
        for c in fm['classes'] + fm.get('classes_inferred', []):
            if c not in classes: errs.append('%s: unknown class %s' % (rel, c))
        if set(fm.get('classes_inferred', [])) & set(fm['classes']): errs.append('%s: a class is both human and inferred' % rel)
        if fm['status'] == 'analyzed' and fm['tagged_by'] != 'manual': errs.append('%s: analyzed but not manually tagged' % rel)
        if fm['status'] == 'analyzed' and not s.strip('_(none yet)_ \n'): errs.append('%s: analyzed without summary' % rel)
    if errs: print('\n'.join(errs[:80])); print('%d error(s)' % len(errs)); sys.exit(1)
    print('ok: all records valid')

def cmd_index(a):
    tax = load_tax(); classes = load_classes()
    byclass = collections.defaultdict(list); byfacet = collections.defaultdict(lambda: collections.defaultdict(list)); work = collections.defaultdict(list)
    cnt = collections.Counter()
    for k, p in all_records():
        fm, s, nt = parse(p); ref = label(fm, k, p)
        link = '[%s](../%s)' % (ref, os.path.relpath(p, ROOT))
        for c in fm['classes']: byclass[c].append((link, fm['status'], fm['title']))
        if fm['tagged_by'] == 'manual':
            for t in fm['tags']:
                f, v = t.split(':', 1); byfacet[f][v].append(link)
        elif fm['status'] in ('triaged', 'stub') and len(work[k]) < 60: work[k].append('%s %s' % (link, fm['title'][:80]))
    L = ['# By problem class\n', 'Generated by `pz index`. Records linked to each class (any status).\n']
    for c in sorted(byclass, key=lambda x: (x[0], int(x[1:]))):
        L.append('\n## %s — %s\n' % (c, classes.get(c, {}).get('title', '?')))
        for link, st, title in sorted(byclass[c]): L.append('- %s `%s` %s' % (link, st, title[:90]))
    open(os.path.join(ROOT, 'indexes', 'by-class.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    L = ['# By facet (manually tagged records only)\n', 'Generated by `pz index`.\n']
    for f in tax:
        if f not in byfacet: continue
        L.append('\n## %s\n' % f)
        for v in sorted(byfacet[f], key=lambda v: -len(byfacet[f][v])):
            L.append('- **%s** (%d): %s' % (v, len(byfacet[f][v]), ' '.join(byfacet[f][v][:40]) + (' …' if len(byfacet[f][v]) > 40 else '')))
    open(os.path.join(ROOT, 'indexes', 'by-facet.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    L = ['# Worklist (next records not yet manually analyzed)\n']
    for k in ('issue', 'commit'):
        L.append('\n## %ss\n' % k); L += ['- ' + x for x in work[k]]
    open(os.path.join(ROOT, 'indexes', 'worklist.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    byk, c, cursors = stats(); L = ['# Status\n', 'Generated by `pz index`.\n', '| kind | total | stub | triaged | read | analyzed |', '|---|---|---|---|---|---|']
    for k in ('issue', 'commit'): L.append('| %s | %d | %s |' % (k, sum(byk[k].values()), ' | '.join(str(byk[k].get(s, 0)) for s in STATUS_ORDER)))
    open(os.path.join(ROOT, 'indexes', 'STATUS.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    # constraints catalog: rules a typed strategy layer must enforce, with our own summaries
    tax2 = tax.get('constraint', {}).get('values', {}); cat = collections.defaultdict(list)
    for k, p in all_records():
        fm, sm, nt = parse(p)
        for t in fm['tags']:
            if t.startswith('constraint:'):
                ref = label(fm, k, p)
                cat[t.split(':', 1)[1]].append('- [%s](../%s) `z2:%s` %s' % (ref, os.path.relpath(p, ROOT), ([x.split(':',1)[1] for x in fm['tags'] if x.startswith('z2:')] or ['unverified'])[0], sm.replace('\n', ' ')))
    L = ['# Constraints catalog (seed)\n', 'Rules a typed strategy layer must enforce. Generated by `pz index` from records tagged `constraint:*`.',
         'Each line is our own summary of an issue/commit; verify against the linked record before encoding a rule.\n']
    for v in sorted(cat, key=lambda v: -len(cat[v])):
        L.append('\n## %s — %s (%d)\n' % (v, tax2.get(v, ''), len(cat[v]))); L += cat[v]
    open(os.path.join(ROOT, 'indexes', 'constraints.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    # stats over the manually tagged corpus
    for _repo, _fn in (('z1', 'stats.md'), ('z2', 'stats-z2.md')):
        C = collections.defaultdict(collections.Counter); yr = collections.defaultdict(collections.Counter); tot = collections.Counter()
        for k, p in all_records(repo=_repo):
            fm, sm, nt = parse(p)
            if fm['tagged_by'] != 'manual': continue
            tot[k] += 1
            for t in fm['tags']:
                f, v = t.split(':', 1); C[(k, f)][v] += 1
            if k == 'issue':
                kd = [t.split(':', 1)[1] for t in fm['tags'] if t.startswith('kind:')]
                yr[fm['date'][:4]][kd[0] if kd else 'untagged'] += 1
        L = ['# Corpus statistics (' + _repo + ', manually tagged records)\n', 'Generated by `pz index`. Counts are records carrying a tag; multi-valued facets can sum above the record count.',
             'Issue depth `thread` means title + opening post + the first maintainer replies were read (long threads are truncated); commits are subject + file level.\n',
             '- issues tagged: %d, commits tagged: %d\n' % (tot['issue'], tot['commit'])]
        def table(k, f, n=12):
            rows = C[(k, f)].most_common(n)
            if not rows: return
            L.append('\n### %s: %s\n' % (k, f)); L.append('| value | records |'); L.append('|---|---|')
            for v, c in rows: L.append('| %s | %d |' % (v, c))
        for f in ('kind', 'outcome', 'layer', 'cause', 'os', 'target', 'impact', 'conf', 'constraint'): table('issue', f, 15 if f == 'cause' else 12)
        for f in ('ctype', 'engine', 'layer', 'cause'): table('commit', f, 12)
        L.append('\n### issues by year and kind\n'); kinds = sorted({v for c in yr.values() for v in c})
        L.append('| year | ' + ' | '.join(kinds) + ' | total |'); L.append('|---|' + '---|' * (len(kinds) + 1))
        for y in sorted(yr): L.append('| %s | ' % y + ' | '.join(str(yr[y].get(v, 0)) for v in kinds) + ' | %d |' % sum(yr[y].values()))
        open(os.path.join(ROOT, 'indexes', _fn), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
        if _repo == 'z2': print('indexes written')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('bootstrap'); s.add_argument('--corpus', choices=['z1', 'z2'], default='z1'); s.add_argument('--issues', required=True); s.add_argument('--clone', required=True)
    s.add_argument('--heuristics', choices=['none', 'zapret'], default='none', help='none = leave tags empty (generic); zapret = the example keyword rules for the source project'); s.set_defaults(f=cmd_bootstrap)
    sp.add_parser('classes-build').set_defaults(f=cmd_classes_build)
    sp.add_parser('backfill-docs').set_defaults(f=cmd_backfill_docs)
    s = sp.add_parser('check'); s.add_argument('batch'); s.set_defaults(f=cmd_check)
    s = sp.add_parser('stamp'); s.add_argument('file'); s.set_defaults(f=cmd_stamp)
    s = sp.add_parser('apply'); s.add_argument('batch'); s.add_argument('--name'); s.set_defaults(f=cmd_apply)
    sp.add_parser('replay').set_defaults(f=cmd_replay)
    s = sp.add_parser('next'); s.add_argument('--kind', choices=['issue', 'commit']); s.add_argument('--status', default='stub,triaged,read')
    s.add_argument('--repo', default='z1', choices=['z1', 'z2']); s.add_argument('-n', type=int, default=30); s.add_argument('--after', type=int); s.add_argument('--width', type=int, default=90); s.set_defaults(f=cmd_next)
    s = sp.add_parser('show'); s.add_argument('ref'); s.set_defaults(f=cmd_show)
    s = sp.add_parser('status'); s.add_argument('--write', action='store_true'); s.set_defaults(f=cmd_status)
    sp.add_parser('validate').set_defaults(f=cmd_validate)
    sp.add_parser('index').set_defaults(f=cmd_index)
    a = ap.parse_args(); a.f(a)

if __name__ == '__main__':
    main()
