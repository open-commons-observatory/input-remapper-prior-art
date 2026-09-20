#!/usr/bin/env python3
"""rulegen — build a tagging batch from explicit subject-pattern rules, so no ref is ever typed by hand.

  rulegen.py RULES.py --corpus z1|z2 [--kind commit|issue] --n 120 --out batches/0073-name.tsv --header "commits 366..475, Jan 2026"

RULES.py defines   R = [(regex, "facet:value facet:value", "Summary in your own words."), ...]
Rules are tried in order (specific first); the first regex that matches the record's title wins. Records that match no rule
are printed as UNMATCHED: add a rule or write those lines by hand. The rules are copied into the batch header as comments,
so the archive shows exactly how the tags were assigned. Only records not yet `analyzed` are considered, in id order.
Every line carries depth=<--depth> (default title): pattern rules over titles or subjects are title-depth evidence.
Apply the result with:  pz.py check BATCH && pz.py apply BATCH && pz.py validate   (no pipes: keep the exit status).
"""
import argparse, os, re, runpy, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pz  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rules'); ap.add_argument('--corpus', default='z1', choices=['z1', 'z2']); ap.add_argument('--kind', default='commit', choices=['commit', 'issue'])
    ap.add_argument('--n', type=int, default=100); ap.add_argument('--out', required=True); ap.add_argument('--header', default=''); ap.add_argument('--with-state', action='store_true', help='match the rules against the title plus [state] (pr-merged, pr-closed, closed/completed, ...): for PR-heavy projects'); ap.add_argument('--depth', default='title', choices=['title', 'thread', 'full', 'source'], help='how deeply the records were READ; rules over titles must say title (apply would otherwise default issues to thread)')
    a = ap.parse_args()
    R = runpy.run_path(a.rules)['R']
    todo = []; states = {}
    for k, p in pz.all_records(a.kind, repo=a.corpus):
        fm, s, nt = pz.parse(p)
        states[fm['id']] = fm.get('state', '')
        if fm['status'] != 'analyzed':
            todo.append((fm['id'], fm.get('hash'), fm['title']))
    todo.sort(key=lambda x: x[0]); todo = todo[:a.n]
    pre = ('z2' if a.corpus == 'z2' else '') + ('c' if a.kind == 'commit' else 'i')
    groups, unmatched = {}, []
    for cid, h, t in todo:
        ref = pre + (h if a.kind == 'commit' else str(cid))
        for rx, tags, summ in R:
            if re.search(rx, t + ((' [' + states[cid] + ']') if a.with_state and cid in states else ''), re.I):
                groups.setdefault((tags, summ), []).append(ref); break
        else:
            unmatched.append((ref, t))
    lines = ['# ' + (a.header or 'pattern-rule batch'), '# Method: subject-pattern rules applied by script (regex -> tags and summary); depth as tagged.']
    lines += ['# rule: /%s/ -> %s' % (rx, tags) for rx, tags, _ in R]
    for (tags, summ), refs in groups.items():
        for i in range(0, len(refs), 12):
            lines.append(','.join(refs[i:i + 12]) + ' | - | ' + tags + ' depth=' + a.depth + ' | ' + summ)
    open(a.out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('considered %d | matched %d | unmatched %d -> %s' % (len(todo), len(todo) - len(unmatched), len(unmatched), a.out))
    for ref, t in unmatched:
        print('  UNMATCHED', ref, t[:90])


if __name__ == '__main__':
    main()
