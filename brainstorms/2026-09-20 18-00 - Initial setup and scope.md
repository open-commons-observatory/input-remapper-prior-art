# 2026-09-20 18-00 - Initial setup and scope

**Project:** sezanzeb/input-remapper prior-art analysis under open-commons-observatory
**Owner instructions:** use the prior-art-playbook; analyse all issues; group, triage, form PRs to close them; improve the playbook as we go; record every decision here for the next session.
**Repo:** https://github.com/open-commons-observatory/input-remapper-prior-art
**Playbook:** https://github.com/sync-dot-mesh/prior-art-playbook

---

## Done

- Read the playbook in full: README, all 26 procedures, principles, goals, maturity, pitfalls, taxonomy example, batch format, data model, summary style, all tools.
- Checked the zapret-prior-art reference implementation for structural reference.
- Surveyed input-remapper: ~5 950 stars, ~1 370 total issues/PRs (369 open as of 2026-09-20), one primary maintainer (sezanzeb, ~84% of commits), Python + GTK + evdev + uinput.
- Created `open-commons-observatory/input-remapper-prior-art` repository (public).
- Scaffolded from the reference implementation: all tools (pz.py, threads.py, rulegen.py, textrules.py, review.py, registry.py), CI workflow, gitignore, taxonomy, registry source stubs, directory stubs, brainstorms index.
- Wrote `analysis/00-scope.md` (P00): goals G2 + G6 + G9; 10 questions; depth plan (issues `full`, commits `title`); out-of-scope list.
- Drafted `taxonomy/facets.json` (P05 first draft): 11 facets including the new `pr_potential` facet.
- Wrote `PLAN.md` with procedure checklist.

## Decisions made (with reasoning)

### D1 — Goal preset: G2 + G6 + G9

Considered G1 (quick landscape) but rejected: the owner wants PRs, which requires full reads not titles. G2 (exhaustive) is the base. G6 (support/docs burden) adds doc-gap tagging to find issues closeable by a docs update alone. G9 is a new preset proposed for the playbook: it adds the `pr_potential` facet and a PR triage table as a deliverable.

### D2 — New facet: pr_potential

Not in the playbook vocabulary. The goal "form PRs to close each issue" requires a per-record actionability score. Seven values: code-fix, docs-fix, needs-design, upstream-dep, close-duplicate, wontfix, unknown. Assessed with conf:inferred by default; only a maintainer statement or a merged PR upgrades it. This facet is goal-specific (not proposed for the generic taxonomy starter).

### D3 — No secondary corpus at start

The fork grenudi/input-remapper shares the upstream issue tracker (GitHub forks do not get separate issues). The fork is the contribution vehicle, not a second corpus. z2 deferred to session 5+; the project.json secondary field is pre-filled but unused until then.

### D4 — Maintainer list: sezanzeb + jonasBoss

sezanzeb has 269 of ~320 commits — clearly primary. jonasBoss (27 commits) also reviews PRs and answers issues. Both listed in project.json maintainers. Drive-by contributors are not maintainers.

### D5 — Taxonomy is a first draft; commit to refinement at issue 100

P05 says: sample 100 titles before fixing values. Since the issue list has not been fetched yet, the taxonomy is a reasoned first draft based on knowledge of the project domain. First 100 titles (next session) will drive a refinement batch before the main reading loop.

### D6 — Issues depth: full from the start

With ~1 370 total items and roughly 250 tokens per maintainer reply, the total is within budget for full reads. Using thread depth would require an audit (P10) to repair hidden maintainer text. Full reads from the start avoid the pitfall the first zapret run paid for (pitfall 1).

### D7 — Commits deferred

Commit triage (P07, P11) deferred until issue reading is complete. Issues are the primary data source for PR formation; commits verify fixes and identify patterns.

### D8 — systemd as de_os value

Hold until first 30 issues are read. If service-unit-issue symptom clusters on systemd-specific causes, add systemd to de_os. The service-unit-issue symptom tag covers the observable symptom in the meantime.

## Playbook improvements made in this session

1. Added G9 (PR triage) goal preset to goals.md — a new preset for projects where the end goal is actionable PRs, not just a dataset or rule catalogue.
2. Added lesson 64 to pitfalls.md — a new goal (contribution / PR formation) needs a new facet (pr_potential); design it before the reading loop, not after. The facet is goal-specific; do not add it to the starter taxonomy.
3. Updated MATURITY.md — third project trial started (input-remapper, this session).

## Findings

No issues have been read yet. No findings.

## Limits and open questions

- Taxonomy not yet validated against real titles; first 100 titles will refine it.
- pr_potential values are provisional; may need a new value after the first 50 reads.
- Should de_os include systemd? Decide after first 30 issues.
- Should the auto facet (detect+handle potential) be included? Hold: the goal is PRs, not a rules catalogue.

## What comes next (session 2)

1. P03: python3 tools/threads.py list --corpus z1 -> data/issues-list.json
2. Verify count against GitHub web count (open_issues field in the API)
3. P03: fetch first chunk of threads via fullfetch (chunks of 150, resumable)
4. P04: clone sezanzeb/input-remapper locally
5. P06: bootstrap records (python3 tools/pz.py bootstrap --corpus z1 ...)
6. P05: read first 100 titles and refine taxonomy
7. Start P08/P09 reading loop, round 1 of 12 issues
