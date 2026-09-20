# 00 — Goals and scope

## Decision and deliverable

A tagged, grouped dataset of every issue and PR in `sezanzeb/input-remapper`, from which we produce:
1. A problem registry — one entry per recurring problem class with evidence, frequency and mechanism.
2. A PR triage table — for each open issue (and resolvable closed one), a `pr_potential` tag marking whether a code change, docs update, duplicate-close, or design discussion would close it, and in what fork branch.

Deliverable is the dataset + registry + a prioritised PR queue. The fork `grenudi/input-remapper` is where code changes land.

## Goal presets

**G2** (Exhaustive dataset) + **G6** (Support/docs burden) + **G9** (PR triage — new preset; see playbook goals.md).

## Questions the dataset must answer

1. What are the most common failure modes reported by users, grouped by mechanism?
2. Which issues are caused by user config errors vs genuine bugs vs missing features?
3. Which open issues have a clear, self-contained fix that can land as a PR without maintainer design input?
4. Which issues are Wayland-specific and require upstream protocol work?
5. How many issues are duplicates of each other, and what are the canonical roots?
6. Which device types (keyboard, gamepad, mouse) have the highest bug density?
7. What proportion of issues are answered by existing documentation but reporters missed it?
8. What is the no-maintainer-reply rate, and is it clustered by topic?
9. Which macros/combination features have the most open reports? Is there a single design fix?
10. How has the issue pattern changed over time (X11 → Wayland transition)?

## Item types

| Type | In scope | Depth plan |
|---|---|---|
| Issues | All (open + closed) in sezanzeb/input-remapper | `full` (entire thread via API) |
| Pull Requests | All PRs (share the issue numbering) | `full` |
| Commits (z1) | All commits in sezanzeb/input-remapper | `title` (subject + file list); `source` for constraint-bearing commits |
| GitHub Discussions | OUT OF SCOPE | Not in REST issues API; too sparse to justify |
| Wiki | OUT OF SCOPE | Read as background only; not tagged as records |

## Out of scope (written now so limits are visible at the end)

- GitHub Discussions (not in REST issues API)
- The wiki (used as background reading, not as records)
- Issues in any downstream forks other than grenudi/input-remapper
- Code review comments on PRs (counted as part of the PR thread record)
- External forum threads, Reddit, Discord

## Depth budget

- Issues/PRs: **`full`** — the entire thread fetched via API. Input-remapper has ~1 370 total items (as of 2026-09-20); full reads are feasible in batch rounds of 12.
- Commits: **`title`** by default (subject + file list, no diff). Commits in the `macro`, `injector`, or `combination` layer that are tagged `constraint:*` get promoted to `source` (diff read) in a later pass.

## Honesty checks planned

- P10 hidden-text audit after the first corpus is fetched (compare cached comment count with API ncomments)
- P18 sample re-reads: 5 random records re-read against thread each session
- P22 limits statement in README before any summary is published

## Timebox

Target: 30–50 rounds of 12 issues each for the full read (≈ 360–600 issues per session block). Commit triage deferred until issue reading is complete.

## Scope notes (known limits at start)

- sezanzeb is the single primary maintainer (269 of ~320 total commits); stated findings will rest heavily on one expert.
- The project history begins 2020-10-26; early X11-only issues may not be representative of the current Wayland-active user base.
- `pr_potential` is assessed by one reader with no prior deep input-remapper code knowledge; mark `conf:inferred` until a maintainer confirms.
