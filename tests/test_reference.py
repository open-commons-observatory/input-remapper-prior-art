#!/usr/bin/env python3
"""Offline regression test of the reference implementation (no network, no token): a synthetic git repository and a synthetic
issue list are pushed through bootstrap, rule-tagging, strict apply (atomic rejection, append idempotence, inferred classes),
stamp, review, registry generation and a from-scratch replay. Run:  python tests/test_reference.py   (exit 1 on any failure)."""
import hashlib, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); IMPL = os.path.dirname(HERE)
fails = []


def check(cond, msg):
    print(('ok   ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)


def sh(cmd, cwd, env=None, ok=True):
    r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, env=env)
    if ok and r.returncode: print(r.stdout, r.stderr); raise SystemExit('command failed: ' + cmd)
    return r


def tree_hash(d):
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(d)):
        for f in sorted(files):
            h.update(f.encode()); h.update(open(os.path.join(root, f), 'rb').read())
    return h.hexdigest()


tmp = tempfile.mkdtemp(); env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
try:
    # synthetic upstream repository (unicode, pipes and a merge commit on purpose)
    up = os.path.join(tmp, 'upstream'); os.makedirs(up); sh('git init -q -b main', up, env)
    subjects = ['Initial import', 'Add option --foo | pipe in subject', 'Fix crash on empty input (#3)', 'docs: update README', 'Bump version to 1.2.0', 'Refactor parser',
                'Fix wrong exit code', 'Add support for Ünïcode paths', 'CI: add workflow', 'Update dependencies']
    for i, sj in enumerate(subjects):
        f = 'README.md' if sj.startswith('docs') else 'src/main.c'
        os.makedirs(os.path.join(up, 'src'), exist_ok=True); open(os.path.join(up, f), 'a').write('line %d\n' % i); sh('git add -A && git commit -q -m "%s"' % sj, up, env)
    sh('git checkout -q -b side && echo x > side.txt && git add -A && git commit -q -m "side work" && git checkout -q main && git merge -q --no-ff side -m "Merge branch side"', up, env)
    issues = [{'n': i, 'title': t, 'state': st, 'reason': rs, 'created': '2024-0%d-1%d' % (1 + i % 9, i % 9), 'closed': '', 'author': 'u', 'comments': 0, 'pr': pr, 'merged': mg, 'labels': []}
              for i, (t, st, rs, pr, mg) in enumerate([
                  ('Crash when input is empty', 'CLOSED', 'COMPLETED', False, False), ('How do I pass options | with pipe?', 'CLOSED', None, False, False),
                  ('Add --foo option', 'OPEN', None, False, False), ('Fix crash on empty input', 'CLOSED', None, True, True), ('Try something', 'CLOSED', None, True, False),
                  ('Ünïcode title', 'OPEN', None, True, False)], 1)]
    # project skeleton
    proj = os.path.join(tmp, 'proj'); shutil.copytree(IMPL, proj, ignore=shutil.ignore_patterns('tests', '__pycache__', '.cache'))
    json.dump({'owner': 'o', 'primary': 'p', 'secondary': 'p', 'maintainers': ['m']}, open(os.path.join(proj, 'project.json'), 'w'))
    os.makedirs(os.path.join(proj, 'data'), exist_ok=True); json.dump(issues, open(os.path.join(proj, 'data', 'issues-list.json'), 'w'))
    PZ = 'python3 tools/pz.py'
    sh('%s bootstrap --corpus z1 --issues data/issues-list.json --clone %s' % (PZ, up), proj)
    check(len(os.listdir(os.path.join(proj, 'records', 'issues'))) == 6, 'bootstrap creates one record per issue/PR (6)')
    check(len(os.listdir(os.path.join(proj, 'records', 'commits'))) == 12, 'bootstrap creates one record per commit (12, merge included)')
    check(sh(PZ + ' validate', proj).returncode == 0, 'validate passes on stubs')
    # rule-tagged commits with explicit depth, no unmatched
    open(os.path.join(tmp, 'rc.py'), 'w').write("R=[(r'^Merge','ctype:maintenance','Merge.'),(r'^docs|README','ctype:docs','Docs.'),(r'^Fix|crash','ctype:fix','Fix.'),(r'^Add','ctype:feature','New.'),(r'.','ctype:maintenance','Other.')]")
    r = sh('python3 tools/rulegen.py %s --corpus z1 --kind commit --n 100 --out batches/0001-c.tsv' % os.path.join(tmp, 'rc.py'), proj); check('unmatched 0' in r.stdout, 'rulegen matches every commit')
    check(sh('%s check batches/0001-c.tsv' % PZ, proj).returncode == 0, 'check passes on the generated batch')
    sh('%s apply batches/0001-c.tsv' % PZ, proj)
    # issues from titles + state: depth must stay title
    open(os.path.join(tmp, 'ri.py'), 'w').write("R=[(r'\\[pr-merged\\]','outcome:fixed','Merged PR.'),(r'\\[pr-closed\\]','outcome:wontfix','Closed PR.'),(r'.','kind:meta','Other.')]")
    sh('python3 tools/rulegen.py %s --corpus z1 --kind issue --n 100 --with-state --out batches/0002-i.tsv' % os.path.join(tmp, 'ri.py'), proj); sh('%s apply batches/0002-i.tsv' % PZ, proj)
    fm = open(os.path.join(proj, 'records', 'issues', '0004.md'), encoding='utf-8').read()
    check('"depth": "title"' in fm or 'depth: "title"' in fm, 'title-only rules leave issue depth at title')
    check('outcome:fixed' in fm, 'a merged PR is tagged from its state with --with-state')
    # atomic rejection
    before = tree_hash(os.path.join(proj, 'records')); bad = os.path.join(proj, 'batches', '0003-bad.tsv')
    open(bad, 'w').write('i1 | - | kind:bug outcome:fixed | ok line\ni2 | - | kind:nonsense | bad line\n')
    r = sh('%s apply batches/0003-bad.tsv' % PZ, proj, ok=False); check(r.returncode != 0 and 'REJECTED' in r.stdout, 'a bad tag rejects the whole batch')
    check(tree_hash(os.path.join(proj, 'records')) == before, 'nothing is written when a batch is rejected')
    os.remove(bad)
    # append idempotence + full-depth manual batch + inferred class
    json.dump({'X1': {'title': 'Crash on odd input', 'doc': 'analysis/10-x.md'}}, open(os.path.join(proj, 'taxonomy', 'classes.json'), 'w'))
    open(os.path.join(proj, 'batches', '0003-m.tsv'), 'w').write('i1 | X1 | kind:bug outcome:fixed conf:stated depth=full | The reported crash was fixed.\ni1 | - | depth=full | + Deep read: the maintainer states the cause.\ni2 | ~X1 | kind:question | A question.\n')
    sh('%s apply batches/0003-m.tsv' % PZ, proj); sh('%s apply batches/0003-m.tsv' % PZ, proj)
    t = open(os.path.join(proj, 'records', 'issues', '0001.md'), encoding='utf-8').read()
    check(t.count('+ Deep read') == 0 and t.count('Deep read: the maintainer states the cause.') == 1, 'an appended note is idempotent (applied twice, present once)')
    t2 = open(os.path.join(proj, 'records', 'issues', '0002.md'), encoding='utf-8').read()
    check('classes_inferred' in t2 and 'X1' in t2, 'a ~class is stored as classes_inferred')
    check(sh(PZ + ' validate', proj).returncode == 0, 'validate passes after manual batches')
    # stamp, review, registry
    open(os.path.join(proj, 'README.md'), 'w').write('# t\n<!-- status:begin -->\n<!-- status:end -->\n'); sh(PZ + ' stamp README.md', proj)
    check('z1 issues: 6' in open(os.path.join(proj, 'README.md')).read(), 'stamp fills computed counts')
    sh('python3 tools/review.py --maintainers m', proj); check(os.path.exists(os.path.join(proj, 'indexes', 'review.md')), 'review writes indexes/review.md')
    json.dump({'docs': [{'file': '10-x.md', 'title': '10 - X', 'intro': 'Intro.', 'entries': ['X1']}], 'problems': {'X1': {'title': 'Crash on odd input', 'area': 'X', 'doc': '10-x.md', 'pre': '', 'first_pass_evidence': [],
               'findings': ['- **Symptom:** a crash.'], 'proposals': ['- **Auto-catch:** fuzz.']}}}, open(os.path.join(proj, 'registry', 'source', 'problems.json'), 'w'))
    os.makedirs(os.path.join(proj, 'analysis'), exist_ok=True); sh('python3 tools/registry.py generate', proj)
    check(all(os.path.exists(os.path.join(proj, x)) for x in ('registry/X1.md', 'registry/README.md', 'registry/by-symptom.md', 'analysis/10-x.md')), 'registry generate writes pages, index, by-symptom and the document view')
    # from-scratch replay reproduces the records
    want = tree_hash(os.path.join(proj, 'records')); shutil.rmtree(os.path.join(proj, 'records')); os.makedirs(os.path.join(proj, 'records'))
    sh('%s bootstrap --corpus z1 --issues data/issues-list.json --clone %s' % (PZ, up), proj); sh(PZ + ' replay', proj)
    check(tree_hash(os.path.join(proj, 'records')) == want, 'bootstrap + replay reproduces every record byte for byte')
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print('\n%s (%d failures)' % ('ALL PASSED' if not fails else 'FAILED', len(fails))); sys.exit(1 if fails else 0)
