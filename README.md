# input-remapper-prior-art

Prior-art analysis of [`sezanzeb/input-remapper`](https://github.com/sezanzeb/input-remapper) — a Linux input-device remapping tool (~5 950 stars, ~1 370 total issues, actively maintained by one primary author).

**Goal (G2 + G6 + G9):** read every issue at full depth, tag and group into recurring problems, triage each group, and produce a set of actionable PRs that close open issues. Carried out by Volodymyr Kanishchev (@grenudi) under the [open-commons-observatory](https://github.com/open-commons-observatory) organisation; fork at [`grenudi/input-remapper`](https://github.com/grenudi/input-remapper).

Method: [sync-dot-mesh/prior-art-playbook](https://github.com/sync-dot-mesh/prior-art-playbook) (proven on zapret, this is the third project trial).

<!-- status:begin -->
<!-- status:end -->

## Layout

```
analysis/00-scope.md      goal, questions, depth budget, out-of-scope list
PLAN.md                   ticked procedure checklist
brainstorms/              dated session entries
records/issues/           one file per issue/PR
records/commits/          one file per commit
taxonomy/                 facets.json (controlled vocabulary), classes.json (problem classes)
batches/                  tagging passes (replayable)
indexes/                  generated: by-class, by-facet, worklist, STATUS, stats
data/                     API lists (issues-list.json)
registry/                 problem registry pages (generated)
tools/                    pz.py, threads.py, rulegen.py, textrules.py, review.py, registry.py
```

## Progress
See `brainstorms/README.md` for the session log index and `indexes/STATUS.md` for current counts.

