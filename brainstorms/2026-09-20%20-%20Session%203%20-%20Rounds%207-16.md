# 2026-09-20 - Session 3 - Rounds 7-16 (issues #90-#283)

**Project:** sezanzeb/input-remapper prior-art analysis
**Repo:** https://github.com/open-commons-observatory/input-remapper-prior-art
**Standing instructions:** use prior-art-playbook; read all issues at full depth; group and triage; form PRs; improve playbook.

## Done

- Optimized pattern: --depth 1 clone (23MB), no upstream clone, per-round fetch of 12 threads, persistent git auth header.
- Rounds 7-16: 120 more issues read at full depth (issues #90-#283), batches 0007-0016 applied.
- P16: indexes generated, STATE.json written.
- Total: 192 of 1099 issues/PRs analyzed (17.5%).

## Key findings (issues #90-#283, 2021-04 to 2022-02)

Problem classes solidifying:

1. **Modifier not released after combination on Wayland** (#221, #229, #201): global uinput architecture (v1.4.0) fixed this.
2. **Bluetooth autoload race** (#274 + earlier cluster): udev fires with empty DEVNAME; Bluetooth device not ready. Multiple partial fixes; still not fully resolved.
3. **Fedora install cluster** (#85, #181, #204, #213, #225): 5 issues over 9 months; no official RPM package; pip path issues.
4. **Python version mismatch** (#231, #278): 3.10 upgrade breaks 3.8 installs; slots=True broke 3.8 users.
5. **xmodmap.json empty after config migration** (#258): only GTK app can regenerate it; service cannot.
6. **Project rename to Input Remapper** (#218, #248): resolved name collision with "keymapper".
7. **Macro system expanded**: if_tap/if_single (#183), key_down/key_up (#198), $ variables (#186), macro editor GtkSourceView4 (#109).
8. **Scroll blocked by libinput when cursor moves** (#282): libinput bug, upstream-dep, workaround xdotool.

## Taxonomy: no changes needed. pr_potential working well.

## What comes next (session 4)

git clone --depth 1 the repo, read CHECKPOINT.json. Pick up at issue #284. Continue rounds 17-26 (~120 more). At 300 issues: start problem class clustering.
