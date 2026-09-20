#!/usr/bin/env python3
"""textrules — multi-label tagging of records from keyword rules over their text, written as an auditable batch.

  textrules.py RULES.py --kind issue [--corpus z1|z2|all] [--fields title,summary] [--chars 400] --out BATCH [--report]

RULES.py defines   R = [("facet:value", r"regex"), ...]   (every rule that matches adds its tag; several tags per record)
Only records with at least one match get a line; lines are grouped by identical tag sets. The rules are copied into the
batch header. These are WEAK labels from text: use them for facets that describe what a reader would see (symptom),
not for judgements. --report prints match counts per rule and samples for a quick false-positive check.
Lines carry depth=<--depth> (default title) so weak text labels never raise a record's depth by default.
Apply with:  pz.py check BATCH && pz.py apply BATCH && pz.py validate   (no pipes).
"""
import argparse, collections, os, re, runpy, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pz  # noqa: E402

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rules'); ap.add_argument('--kind', default='issue', choices=['issue', 'commit']); ap.add_argument('--corpus', default='all', choices=['z1', 'z2', 'all'])
    ap.add_argument('--fields', default='title,summary'); ap.add_argument('--chars', type=int, default=400); ap.add_argument('--out', required=True); ap.add_argument('--depth', default='title', choices=['title', 'thread', 'full', 'source']); ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    R = [(t, re.compile(rx, re.I)) for t, rx in runpy.run_path(a.rules)['R']]
    fields = a.fields.split(','); groups = collections.defaultdict(list); per = collections.Counter(); samples = collections.defaultdict(list); n = 0
    for k, p in pz.all_records(a.kind):
        repo = pz.repo_of(p)
        if a.corpus != 'all' and repo != a.corpus: continue
        fm, s, nt = pz.parse(p)
        if fm['tagged_by'] != 'manual': continue
        text = (fm['title'] if 'title' in fields else '') + ' || ' + (s[:a.chars] if 'summary' in fields else '')
        hits = sorted({t for t, rx in R if rx.search(text)})
        for t in hits:
            per[t] += 1
            if len(samples[t]) < 3: samples[t].append(fm['title'][:60])
        if hits:
            ref = ('z2' if repo == 'z2' else '') + ('i%d' % fm['id'] if k == 'issue' else 'c' + fm['hash'])
            groups[tuple(hits)].append(ref); n += 1
    L = ['# multi-label keyword tagging (weak labels from text); fields=%s, first %d characters of the summary' % (a.fields, a.chars)]
    L += ['# rule: %s <- /%s/' % (t, rx.pattern) for t, rx in R]
    for tags, refs in sorted(groups.items()):
        for i in range(0, len(refs), 12): L.append(','.join(refs[i:i + 12]) + ' | - | ' + ' '.join(tags) + ' depth=' + a.depth + ' | ')
    open(a.out, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('records with at least one tag: %d -> %s' % (n, a.out))
    if a.report:
        for t, c in per.most_common(): print('  %-34s %4d   e.g. %s' % (t, c, ' | '.join(samples[t])))

if __name__ == '__main__':
    main()
