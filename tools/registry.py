#!/usr/bin/env python3
"""registry — the problem registry: one entry per recurring problem, findings kept apart from proposals,
evidence / status / symptoms GENERATED from the records, and the thematic documents produced as views.

  registry.py import-docs   # ONE-TIME migration: analysis/NN-*.md (hand-written) -> registry/source/problems.json (+ copies in analysis/first-pass/)
  registry.py generate      # registry/<ID>.md pages, registry/README.md, registry/by-symptom.md, and the analysis/NN-*.md views

Source of truth for the hand-written text is registry/source/problems.json (findings, proposals, first-pass evidence notes) and
registry/source/links.json (problem -> rule ids). Everything else is derived from taxonomy/classes.json and the records
(classes = human-cited, classes_inferred = suggestions from a model; both are shown, marked apart). Never edit generated files.
"""
import argparse, collections, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pz  # noqa: E402

ROOT = pz.ROOT
SRC = os.path.join(ROOT, 'registry', 'source')
PROPOSAL = re.compile(r'^(- \*\*(Auto-catch|Auto-handle|atpret note|atpret notes|For atpret|Invariants for atpret)|\*\*Auto-catch|\*\(Design proposal)')
STALE = re.compile(r'(#\d{1,4}(?:\s*\([^)]*\))?)\s*\[(?:R|T|R-lite|T\s*\+[^\]]*|R/T|T/R-lite|T/R)\]')
DOC_RE = re.compile(r'^(10|20|30|40|50|60|70|80)-.*\.md$')
DEPTH_RANK = {'source': 3, 'full': 2, 'thread': 1, 'title': 0}


def clean(t):
    return STALE.sub(r'\1', t)


def join_blocks(blocks):
    """Blocks that start with a bullet are glued to the previous block with a single newline (as in the originals)."""
    out = ''
    for i, b in enumerate(blocks):
        out += b if i == 0 else (('\n' if b.startswith('- ') else '\n\n') + b)
    return out


def split_blocks(body):
    blocks, cur = [], None
    for line in body.split('\n'):
        if re.match(r'^- |^\*\*[^*\n]+\*\*|^\*\(', line) or cur is None:
            if cur is not None: blocks.append('\n'.join(cur).rstrip())
            cur = [line]
        else:
            cur.append(line)
    if cur is not None: blocks.append('\n'.join(cur).rstrip())
    return [b for b in blocks if b.strip() and b.strip() != '---']


def cmd_import_docs(a):
    os.makedirs(SRC, exist_ok=True); fp = os.path.join(ROOT, 'analysis', 'first-pass'); os.makedirs(fp, exist_ok=True)
    docs, problems = [], {}
    for f in sorted(os.listdir(os.path.join(ROOT, 'analysis'))):
        if not DOC_RE.match(f): continue
        txt = open(os.path.join(ROOT, 'analysis', f), encoding='utf-8').read()
        shutil.copy(os.path.join(ROOT, 'analysis', f), os.path.join(fp, f))
        parts = re.split(r'(?m)^(?=## [A-Z]\d+ \u2014 )', txt)
        intro = parts[0]
        title = re.match(r'# (.+)', intro).group(1)
        # drop the stale evidence legend and the end-of-run banner from the intro; they are regenerated
        intro_lines = [l for l in intro.split('\n')[1:] if not l.startswith('Evidence tags:') and not l.startswith('> **Evidence note (end of run)')]
        intro = re.sub(r'\n{3,}', '\n\n', '\n'.join(intro_lines)).strip('\n')
        ids, pre = [], ''
        for sec in parts[1:]:
            m = re.match(r'## ([A-Z]\d+) \u2014 (.+)', sec); pid, ptitle = m.group(1), m.group(2).strip()
            body = sec.split('\n', 1)[1] if '\n' in sec else ''
            lines = body.rstrip('\n').split('\n'); trail = []
            while lines and (lines[-1].startswith('# ') or not lines[-1].strip() or lines[-1].strip() == '---'):
                if lines[-1].startswith('# '): trail.insert(0, lines[-1])
                lines.pop()
            bl = split_blocks('\n'.join(lines))
            ev = [b for b in bl if b.startswith('- **Evidence')]
            prop = [clean(b) for b in bl if PROPOSAL.match(b)]
            find = [clean(b) for b in bl if b not in ev and not PROPOSAL.match(b)]
            problems[pid] = {'title': ptitle, 'area': pid[0], 'doc': f, 'pre': pre, 'first_pass_evidence': [clean(b) for b in ev],
                             'findings': find, 'proposals': prop}
            ids.append(pid); pre = '\n'.join(trail)
        docs.append({'file': f, 'title': title, 'intro': intro, 'entries': ids})
    json.dump({'docs': docs, 'problems': problems}, open(os.path.join(SRC, 'problems.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('imported %d documents, %d problems' % (len(docs), len(problems)))


def load_records():
    by = collections.defaultdict(lambda: {'human': [], 'inferred': []})
    for k, p in pz.all_records():
        fm, s, nt = pz.parse(p); repo = pz.repo_of(p)
        ref = ('z2#' if repo == 'z2' else '#') + str(fm['id']) if k == 'issue' else '`%s%s`' % ('z2:' if repo == 'z2' else '', fm['hash'])
        rel = os.path.relpath(p, os.path.join(ROOT, 'registry'))
        rec = {'ref': ref, 'kind': k, 'repo': repo, 'date': fm['date'], 'depth': fm['depth'], 'title': fm['title'], 'summary': re.sub(r'\s+', ' ', s).strip(),
               'tags': fm['tags'], 'rel': rel, 'manual': fm['tagged_by'] == 'manual'}
        for c in fm['classes']: by[c]['human'].append(rec)
        for c in fm.get('classes_inferred', []): by[c]['inferred'].append(rec)
    return by


def tagval(rec, facet):
    return [t.split(':', 1)[1] for t in rec['tags'] if t.startswith(facet + ':')]


def summarise(recs):
    d = collections.Counter(r['depth'] for r in recs); z = collections.Counter(v for r in recs for v in tagval(r, 'z2'))
    o = collections.Counter(v for r in recs for v in tagval(r, 'outcome')); sy = collections.Counter(v for r in recs for v in tagval(r, 'symptom'))
    ca = collections.Counter(v for r in recs for v in tagval(r, 'cause')); ys = sorted(r['date'][:4] for r in recs)
    return d, z, o, sy, ca, (ys[0] + '-' + ys[-1] if ys else '')


def rank(r):
    conf = 1 if 'conf:stated' in r['tags'] else 0
    return (-DEPTH_RANK.get(r['depth'], 0), -conf, r['kind'] != 'issue', r['date'])


def fmt_counter(c, n=None):
    return ', '.join('%s %d' % (k, v) for k, v in c.most_common(n)) or '-'


def automation(p):
    lab = ' '.join(b.split('\n')[0] for b in p['proposals'])
    hc, hh = 'Auto-catch' in lab, 'Auto-handle' in lab
    return 'detect+handle' if hc and hh else ('detect-only' if hc else ('handle-only' if hh else 'none'))


def cmd_generate(a):
    data = json.load(open(os.path.join(SRC, 'problems.json'), encoding='utf-8')); P, docs = data['problems'], data['docs']
    links = json.load(open(os.path.join(SRC, 'links.json'), encoding='utf-8')) if os.path.exists(os.path.join(SRC, 'links.json')) else {}
    by = load_records(); reg = os.path.join(ROOT, 'registry'); os.makedirs(reg, exist_ok=True)
    idx = []; sym_by_problem = collections.defaultdict(collections.Counter)
    for pid in sorted(P):
        p = P[pid]; H, I = by[pid]['human'], by[pid]['inferred']; allr = H + I
        d, z, o, sy, ca, span = summarise(allr)
        for s_, n in sy.items(): sym_by_problem[s_][pid] += n
        top = sorted(H, key=rank)[:30] + sorted(I, key=rank)[:10]
        L = ['---', 'id: "%s"' % pid, 'area: "%s"' % p['area'], 'title: %s' % json.dumps(p['title'], ensure_ascii=False),
             'records_human: %d' % len(H), 'records_inferred: %d' % len(I), 'automation: "%s"' % automation(p),
             'rules: %s' % json.dumps(links.get(pid, [])), 'generated: true  # findings/proposals come from registry/source/problems.json, the rest from the records', '---', '',
             '# %s \u2014 %s' % (pid, p['title']), '', '## Findings (first-pass narrative; evidence tags for issues removed, see the generated evidence below)', '']
        L += [join_blocks(p['findings']) or '_(none: the whole entry is a proposal)_', '']
        if p['proposals']:
            L += ['## Proposals (design ideas, not findings)', '', join_blocks(p['proposals']), '']
        if p['first_pass_evidence']:
            L += ['## First-pass evidence note (as written; changelog and source references)', '', join_blocks(p['first_pass_evidence']), '']
        L += ['## Evidence in the dataset (generated)', '',
              '- records cited by hand: **%d**; suggested by the class model: **%d** (marked `~`); years: %s' % (len(H), len(I), span or '-'),
              '- depth: %s' % fmt_counter(d), '- status in zapret2 (where checked): %s' % fmt_counter(z),
              '- outcomes: %s' % fmt_counter(o, 6), '- symptoms: %s' % fmt_counter(sy, 6), '- top causes: %s' % fmt_counter(ca, 6),
              '- rules: %s' % (', '.join('[%s](../analysis/rules.md)' % r for r in links.get(pid, [])) or '-'), '',
              '| record | date | depth | z2 | outcome | summary |', '|---|---|---|---|---|---|']
        for r in top:
            mark = '~' if r in I and r not in H else ''
            L.append('| %s%s | %s | %s | %s | %s | %s |' % (mark, '[%s](%s)' % (r['ref'], r['rel']), r['date'], r['depth'], ','.join(tagval(r, 'z2')) or '-',
                                                          ','.join(tagval(r, 'outcome')) or '-', r['summary'][:110].replace('|', '/')))
        if len(H) + len(I) > len(top): L.append('\n_%d more records not listed (see `indexes/by-class.md`)._' % (len(H) + len(I) - len(top)))
        open(os.path.join(reg, pid + '.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
        idx.append((pid, p, H, I, d, z, sy))
    # index
    T = ['# Problem registry', '',
         'One entry per recurring problem (%d entries; ids are the class ids in `taxonomy/classes.json`). Generated by `tools/registry.py generate`; the hand-written text lives in `registry/source/`.' % len(idx),
         'Records counted per problem: **human** = cited by hand in the analysis, **inferred** = suggested by a model over the tags (marked `~` in the pages). See `by-symptom.md` for the view by what the reporter saw and `../analysis/rules.md` for the rules.', '',
         '| id | problem | records (human/inferred) | zapret2 status | top symptoms | automation idea | rules |', '|---|---|---|---|---|---|---|']
    for pid, p, H, I, d, z, sy in idx:
        T.append('| [%s](%s.md) | %s | %d / %d | %s | %s | %s | %s |' % (pid, pid, p['title'].replace('|', '/'), len(H), len(I), fmt_counter(z, 3), ', '.join(k for k, _ in sy.most_common(2)) or '-',
                                                                   automation(p), ', '.join(links.get(pid, [])) or '-'))
    R = collections.defaultdict(list)
    for pid in links:
        for r in links[pid]: R[r].append(pid)
    T += ['', '## Rules to problems', '', '| rule | problems |', '|---|---|'] + ['| %s | %s |' % (r, ', '.join('[%s](%s.md)' % (x, x) for x in sorted(v))) for r, v in sorted(R.items())]
    thin = [(pid, len(H), len(I)) for pid, p, H, I, d, z, sy in idx if len(H) < 3]
    T += ['', '## Thin evidence', '', 'Problems with fewer than three hand-cited records: their text rests on very little of the tracker data and deserves a second look before anyone relies on it. Some of these entries rest mainly on the documentation or source of the project (see the first-pass evidence note on the page) rather than on tracker threads.', '',
          '| id | problem | human / inferred |', '|---|---|---|'] + ['| [%s](%s.md) | %s | %d / %d |' % (pid, pid, P[pid]['title'].replace('|', '/'), h, i) for pid, h, i in thin]
    open(os.path.join(reg, 'README.md'), 'w', encoding='utf-8').write('\n'.join(T) + '\n')
    # by symptom
    S = ['# By symptom: what the reporter saw, and which problems it usually turns out to be', '',
         'Symptom tags are weak labels derived from the text by keyword rules (estimated precision about two thirds), so read the counts as a search aid. A problem is listed with the number of its records that carry the symptom.', '']
    tax = pz.load_tax().get('symptom', {}).get('values', {})
    tot = collections.Counter(v for by_p in sym_by_problem.values() for v in [])
    for s_ in sorted(sym_by_problem, key=lambda x: -sum(sym_by_problem[x].values())):
        c = sym_by_problem[s_]
        S += ['## %s' % s_, '', '_%s_' % tax.get(s_, ''), '',
              '| problem | records with this symptom |', '|---|---|'] + ['| [%s](%s.md) %s | %d |' % (pid, pid, P[pid]['title'].replace('|', '/'), n) for pid, n in c.most_common(8)] + ['']
    open(os.path.join(reg, 'by-symptom.md'), 'w', encoding='utf-8').write('\n'.join(S) + '\n')
    # documents as views
    for doc in docs:
        O = ['# ' + doc['title'], '', '> **Generated view** of the problem registry (`tools/registry.py generate`; source text in `registry/source/problems.json`).',
             '> Evidence for issues and commits is computed from the records (depth, status in zapret2, symptoms) and linked per problem in `registry/`. Tags `[D]` (docs or source read) and `[C]` (changelog or commit subject) are first-pass notes.',
             '> Sections under **Proposals** are design ideas, not findings.', '', doc['intro'], '']
        for pid in doc['entries']:
            p = P[pid]; H, I = by[pid]['human'], by[pid]['inferred']; d, z, o, sy, ca, span = summarise(H + I)
            if p.get('pre'): O += [p['pre'], '']
            O += ['## %s \u2014 %s' % (pid, p['title']), '', join_blocks(p['findings']) if p['findings'] else '_(this entry is a design proposal)_', '']
            if p['proposals']: O += ['**Proposals (not findings):**', '', join_blocks(p['proposals']), '']
            if p['first_pass_evidence']: O += ['**First-pass evidence note (as written):**', '', join_blocks(p['first_pass_evidence']), '']
            top = ', '.join(r['ref'] for r in sorted(H, key=rank)[:8])
            O += ['**Evidence in the dataset (generated):** %d records cited by hand, %d suggested; depth %s; zapret2 status %s; symptoms %s. Top records: %s. Full list: [registry/%s.md](../registry/%s.md).' %
                  (len(H), len(I), fmt_counter(d), fmt_counter(z), fmt_counter(sy, 3), top or '-', pid, pid), '']
        open(os.path.join(ROOT, 'analysis', doc['file']), 'w', encoding='utf-8').write('\n'.join(O).rstrip('\n') + '\n')
    print('generated %d registry pages, index, by-symptom view and %d document views' % (len(idx), len(docs)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('import-docs').set_defaults(f=cmd_import_docs); sp.add_parser('generate').set_defaults(f=cmd_generate)
    a = ap.parse_args(); a.f(a)


if __name__ == '__main__':
    main()
