# Plan

Make the workout dashboard a calm, visual overview with progressive disclosure. Keep charts, a compact data-health indicator, and weekly feedback prominent; move maintenance and detailed analysis controls out of the default scan path without changing calculations or data safety.

## Scope
- In: compact managed toolbar and Data menu, fewer visible analysis tabs, quiet clickable lift/block headings, concise card copy, collapsed detailed notes and methodology, accessible keyboard navigation, GUI regressions, documentation, versioned build, commit and push.
- Out: new metrics or predictions, source selection/consolidation changes, private-data edits, automatic installation, PR/merge.

## Action items
[x] Inspect README, Local-File-Workflow, desktop/navigation, managed loading, dashboard cards, theme, and existing GUI tests.
[x] Consolidate normal managed mode into one compact toolbar; move refresh/workspace/source controls into Data and retain actionable error/feedback notices.
[x] Keep Dashboard, Training timeline and Explore exercise visible; put secondary analysis/context views in More with a clear active-view indicator.
[x] Simplify lift/block cards and supporting sections using quiet, keyboard-operable drill-down targets and on-demand details; preserve coverage, units, exact variations and missing-data semantics.
[x] Add regression tests for menu reachability, advanced navigation, unsaved feedback, card interactions, hidden details and small-window/background layout.
[x] Update README and Local-File-Workflow, bump version metadata, run targeted/full tests and visual QA at 1120×820 and 900×680, then package and smoke/signature-check the app.
[x] Commit and push scoped changes with save-branch; leave private data and generated builds out of Git.

## Open questions
- None. The user wants fewer visible controls, not removed functionality. Keep important warnings discoverable and explicit, and preserve original inputs and saved feedback. The installed copy remains unchanged until replacement is requested.

## Verification notes
- `scripts/test.sh`: all 175 tests passed. Six card tests also passed after final label polish. `git diff --check`, packaged GUI smoke test, and deep/strict code-signature verification passed.
- Updated `tests/test_managed_gui.py` for compact toolbar, Data-menu actions, secondary-view navigation, visible errors and preserved unsaved feedback. Added `tests/test_clean_cards.py` for quiet keyboard-operable headings, disclosure, exact metrics, unavailable values and background layout.
- Visual QA: real data at 1120×820 and 900×680, Data/More menus, expanded details and latest-week feedback. Still displays 2,461 completed sets from seven exports; one existing conflict stays visible. QA used read-only archive access and verified the saved annotation hash was unchanged.
- Removed duplicate automatic load/source controls and routine status prose; three primary history tabs remain visible. Secondary views gain a visible active tab when opened. Notes, methodology and exact values share one collapsed section.
- Version 0.9.0/build 12 is packaged separately; the installed 0.8.0 app is unchanged.
