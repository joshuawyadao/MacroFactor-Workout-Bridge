# Plan

Implement the approved A overview → B detailed timeline design with real history data, consistent lift colors, clickable block reports, and source-set drill-down. Reuse the desktop's read-only history pipeline and retain its existing explorer, comparison, and context tools.

## Scope
- In: visual block cards, shared export-relative ranges, aligned exact-variation timelines, saved context, weekly workload, exercise workload bars, source-set details, tests/docs, version 0.7.0 build, commit and push on `codex/block-comparison`.
- Out: guessed muscle attribution (show exercise workload instead), recovery predictions, automated causal insights, source/annotation changes, installing over the running app, PR creation or merge.

## Action items
[x] Inspect README, Local-File-Workflow, history/explorer/chart models, desktop navigation, tests, and build configuration.
[x] Add pure range/block/workload projections and in-memory canonical set details; distinguish missing data, partial ranges, invalid dates, and unequal block lengths.
[x] Build the A overview with consistent lift colors, scrollable block cards, normalized complete-week averages, and exercise workload bars.
[x] Add B aligned timelines, block focus, saved-context toggle, shared range/variation navigation, and accessible set-level drill-down.
[x] Test projections, navigation, context, filtering, reload/invalidation, source immutability, missing/zero values, and minimum-window behavior.
[x] Update README, Local-File-Workflow, and version metadata; run targeted/full tests, compilation, diff checks, visual QA, build/signature/smoke verification.
[x] Save scoped code/tests/docs with save-branch, then report results and any limitations.

## Open questions
- None. Weekly averages use only full Monday–Sunday weeks inside both the selected range and observed export date bounds, including weeks with no logs as zero logged workload, never as confirmed skips. Partial weeks stay visible but are excluded from averages. No muscle counts or recovery claims are inferred. Packaging does not replace the installed app.

## Verification
- The full canonical suite passes all 147 tests. Added `test_progress.py` and `test_timeline_gui.py`; updated `test_explorer_gui.py` for the new card destination while retaining independent explorer coverage. The nine timeline tests also pass after the final scroll-navigation adjustment.
- Compilation and Git diff checks pass. Version 0.7.0 (bundle build 10) builds with the pinned, hash-checked dependencies, passes its packaged GUI smoke test, and verifies with an ad-hoc signature.
- Real-input QA loaded all eight dated coach blocks. Export, workbook, exercise mapping, and private annotation SHA-256 hashes remained unchanged. No private data, screenshots, or generated bundles are committed.
- Inspected overview and timeline at 1120×820 and 900×680, the full overview, focused timeline/workload, and logged-set dialog. Fixed retired widgets overlapping during refresh and preserved the inspected week across context toggles. Long notes stay bounded with full tooltips; small windows scroll.
- README and Local-File-Workflow document ranges, conservative averaging, missing data, descriptive context, in-memory source-set inspection, and deferred muscle attribution. The workspace bundle is built; the installed application is not replaced.
