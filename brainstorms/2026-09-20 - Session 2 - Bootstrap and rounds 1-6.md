# 2026-09-20 - Session 2 - Bootstrap, taxonomy refinement, rounds 1-6

**Project:** sezanzeb/input-remapper prior-art analysis
**Repo:** https://github.com/open-commons-observatory/input-remapper-prior-art
**Standing instructions:** use prior-art-playbook; read all issues at full depth; group and triage; form PRs; improve playbook; record all decisions here.

---

## Done

- P03: Fetched complete issues list via API: 1099 items (840 issues, 259 PRs), #1-#1370, 2020-12-05 to 2026-09-19.
- P04: Cloned sezanzeb/input-remapper: 929 commits, first 2020-10-26.
- P05 refinement: Keyword scan of all 840 issue titles confirmed taxonomy coverage. Added autoload-failure to cause facet (24 issues with "autoload" in title) and openrc to de_os.
- Introduced CHECKPOINT.json for machine-readable session state; updated P23 in the playbook.
- P06: Bootstrap complete: 1099 issue/PR records + 929 commit records. All at status=stub, depth=title.
- CI push confirmed green.
- P03 fullfetch: 400 threads cached (issues 1-400).
- Rounds 1-6: 72 issues read at full depth, batches 0001-0006 applied and pushed.

## Findings (first 72 issues, 2020-12 to 2021-04)

**Problem clusters emerging:**

1. **Install/packaging** (very high frequency early): AUR broken, plugdev missing, deb/systemd dependency, pip path issues on Fedora, ZorinOS polkit failure. Most fixed in early releases. PR potential: docs improvements and init-script packaging remain open.

2. **Autoload failures** (recurring, multi-cause): Service not enabled, config.json corruption, GNOME autostart .desktop missing Type=Application, Bluetooth reconnect not triggering autoload. All three eventually fixed. The Bluetooth reconnect case (#25) needed a udev rule. Core pattern: any new device connection path breaks autoload.

3. **Scroll/EV_REL mapping** (#12, #13): Horizontal scroll buttons (REL_HWHEEL) not mappable. Fixed in 0.6.0. Large cluster of similar reports confirmed this was real.

4. **Per-app preset switching** (recurring wontfix): Every version of this request (#32, #50, #56, #72) gets the same answer: Wayland hides window focus. X11 workaround via CLI + desktop keyboard shortcuts exists. Not fixable without Wayland protocol support.

5. **Device quirks** (#36 tablet, #73 VR controller, #74 gamepad, #76 D-pad): Key-mapper misidentifying devices (tablet as gamepad), incorrect ABS range handling, multi-mode devices. Several bugs fixed in joystick-correct-abs-range branch (0.8.0/0.8.1). Pattern: any device with non-standard ABS_X/Y usage gets misidentified.

6. **Firmware-level keys** (#27 brightness, #60 Hypershift, #64): Keys handled by device firmware or DE never reach evdev. Wontfix / upstream-dep. Consistent pattern.

7. **Macro key-stuck/repeat** (#46, #47, #59): Several reports of keys staying pressed or repeating after macro injection. Multiple distinct root causes; most fixed quickly by maintainer.

8. **Docs gaps dominate question issues**: Uninstall instructions, nested macro syntax, daemon-as-root behavior, lockscreen limitation, CLI usage, Restore-Defaults to re-detect keys, "disable" keyword. High PR potential for docs fixes across these.

## Taxonomy decisions

- `autoload-failure` cause: works well, already used in multiple records.
- `openrc` de_os: used in #15. Correct addition.
- `pr_potential` facet: proving useful. Code-fix/docs-fix split is natural. Wontfix and upstream-dep also natural.
- `systemd` de_os: still not needed; service-unit-issue symptom covers it adequately. Decision: hold.
- `auto` facet: still not needed for these early issues. Decision: hold.

## Playbook improvements made in this session

1. Updated P23 with CHECKPOINT.json pattern for cross-session resumability.
2. Pitfall lesson about CHECKPOINT.json will be filed if a session-resume failure occurs.

## Limits

- 72 of 1099 issues analyzed (7%); all from 2020-12 to 2021-04 (project's first 4 months).
- 400 threads cached; 699 still to fetch.
- Taxonomy not yet locked; will review at issue 200.
- Confidence on pr_potential=code-fix records is all conf:inferred; none confirmed by maintainer.

## What comes next (session 3)

1. Fetch threads 400-600 (200 more).
2. Read rounds 7-18 (issues ~90 to ~210, approx. 144 more).
3. At issue 200: lock taxonomy or extend cause values.
4. After all 840 issues: start problem class clustering.
