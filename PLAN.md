# Analysis plan: sezanzeb/input-remapper

Goal preset(s): G2 + G6 + G9 (PR triage)   Started: 2026-09-20   Owner: grenudi (Volodymyr Kanishchev)
Depth budget: issues/PRs to `full`; commits to `title` (selected commits to `source`)

## Setup
- [x] P00 goals and scope written (`analysis/00-scope.md`)
- [x] P01 token in the environment, rate limit known, no secrets in the repo
- [x] P02 repo scaffolded from reference-implementation (`project.json` filled in)
- [ ] P03 issue/PR list fetched and checked against the API count
- [ ] P04 clone made, history completeness checked
- [x] P05 taxonomy designed from the goals (`taxonomy/facets.json`)
- [ ] P06 records bootstrapped
- [ ] P07 mechanical commits rule-tagged (deferred until issue reading done)

## Reading and tagging
- [ ] P08 batch loop running (round size: 12 for full reads, 36 for commit titles)
- [ ] P09 issues read at depth (target depth: `full`)
- [ ] P10 hidden-text audit done
- [ ] P11 commits triaged (subject + files)
- [ ] P12 selected commit diffs read (selection rule: constraint-tagged + macro/injector/combination layer)

## Synthesis
- [ ] P13 claims verified against fork state (grenudi/input-remapper)
- [ ] P14 constraints catalogue (if constraint facet is populated)
- [ ] P15 analysis documents by problem class
- [ ] P16 indexes and statistics
- [ ] P17 second corpus (grenudi fork commit delta — deferred, assess at session 5+)
- [ ] P24 problem registry (classes as data, symptom facet, generated views)
- [ ] P25 review run (`review.py`), ATTENTION items decided

## Assurance and operations
- [ ] P18 QA pass (validate, overwrite check, retractions listed)
- [x] P19 CI workflow in place (`.github/workflows/validate.yml`)
- [ ] P20 session entry and log written (entry #1 written in brainstorms/)
- [ ] P21 replay from scratch verified (deferred until first batch applied)
- [ ] P22 limits statement written (will be stamped into README)
- [ ] P23 autonomous rounds agreed (round size 12 full / 36 brief; stop on scope question or context limit)

## Scope notes
- In scope: all issues + PRs in sezanzeb/input-remapper; all commits in that repo
- Out of scope: GitHub Discussions, wiki, external forums, downstream forks (except grenudi)
- Known limits at start: single primary maintainer; Wayland issues may cluster in recent years; `pr_potential` assessed by one reader
