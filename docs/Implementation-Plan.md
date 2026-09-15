# Plan

Make Workout History dashboard-first, with squat/bench/deadlift cards and automatic cross-block summaries. Add an exercise-first timeline with search and recent-week filters; retain two-block comparison as an optional advanced view. Reuse existing metrics and keep variations, missing data, and source safety explicit.

## Scope
- In: big-three variation cards, all-block overview, searchable exercise explorer, all-history/4/12/24-week filters anchored to the export, week context, shared chart drawing, source-coverage guidance, tests/docs, version 0.6.0 build, commit and push on the current branch.
- Out: merging different exercise variations, inferred recovery/deloads, source/annotation changes, automatic file selection or archiving, new dependencies, PR creation/merge.

## Action items
[x] Inspect history models, desktop/comparison UI, tests, README, and Local-File-Workflow.
[x] Add pure exercise-family navigation and calendar timeline projections; preserve exact variations, zero versus missing, and unmapped weeks.
[x] Add dashboard cards and chronological cross-block summaries; drill into an exercise with one click.
[x] Add search, family, metric, and time-window filters with automatic block/week context and clear source coverage.
[x] Integrate new default navigation, preserve existing workflows/reload selections, and clear stale views on errors.
[x] Cover models, filtering, cards, navigation, reload/invalidation, empty states, and minimum-size rendering with tests.
[x] Update README, Local-File-Workflow, and version metadata; run full tests, read-only real-input checks, visual QA, build/signature/smoke checks.
[x] Commit and push scoped changes and report the verified build.
[ ] Install after the user closes the existing app, retaining a recoverable backup.

## Prior milestone completion
- PR #15 merged into main as `7e3bf5b` after CI Verify passed and all three addressed review threads were resolved with user approval.
- The old feature branch was deleted locally and remotely. Version 0.4.1 and verified private week layouts were installed with recoverable backups; source workbook and export remained unchanged.

## Open questions
- None. Families are navigation groups only. Default cards choose the most recently logged supported variation and name it explicitly; users can change it. Recent ranges use whole Monday–Sunday weeks ending in the export's latest week, not today's date.

## Dashboard and explorer verification
- All 131 tests pass. Compilation, diff checks, the packaged GUI smoke test, and bundle signature verification pass. README and Local-File-Workflow describe the new default navigation and metric/coverage limits.
- Added pure model and GUI coverage for calendar gaps, real zero values, unmapped weeks, exact exercise variations, recent-export-relative windows, family/search filters, card navigation, block shading, latest-first rows, short-export guidance, reload preservation, invalidation, and minimum-size rendering.
- Verified the new all-time export read-only across the dated coach blocks and calendar weeks. Dashboard defaults selected the most recently logged supported squat, bench, and deadlift variations without combining them. Workbook, CSV, config, and annotation hashes stayed unchanged.
- Inspected dashboard, explorer, and retained A/B comparison at 1120×820 and 900×680. The dashboard scrolls at smaller heights, long labels have full tooltips, and the explorer retains an 85-pixel table viewport with real-data warnings visible at minimum size.
- Version 0.6.0 (bundle build 9) is packaged with an ad-hoc signature. The existing installed 0.5.1 app was still open during the installation check; wait for it to close before replacing it, with a `MacroFactor Workout Bridge-0.5.1-before-dashboard.app` backup.

## Dark-interface verification
- Added theme contrast/calendar/popup tests and comparison regressions for swaps, context navigation, on-demand notes, stale summary clearing, sparse RIR coverage, and minimum-window rendering. The full suite contains 120 passing tests.
- Inspected Weekly Bridge, overview, comparison, context, calendar, and popup rendering at 1120×820 and 900×680. Long saved block notes moved into a read-only dialog to preserve table space. Real-input comparison retains an 82-pixel table viewport at minimum size with the existing warnings visible.
- Source workbook, export, config, and annotation hashes remained unchanged during real-input checks. No calculations, annotation schema, or input files changed.
- Compilation and diff checks pass. Version 0.5.1 (bundle build 8) is built, ad-hoc signed, signature-verified, and passes its GUI smoke test.
- Version 0.5.1 was subsequently installed and smoke-tested with user approval. The previous app is preserved as `MacroFactor Workout Bridge-0.5.0-before-dark-interface.app`. Private data was unchanged.

## Previous comparison verification
- Source, config, and annotation hashes stayed unchanged during real-input GUI comparison checks.
- Visual inspection found the source controls crowding out comparison rows; successful loads now collapse those controls behind Show sources, and long block notes scroll inside a bounded read-only field.
- Actual Qt rendering caught a collision with QWidget's metric method; renamed the chart field and selector and retained a render regression test.
- Long real-world week notes initially expanded rows enough to obscure the comparison. Rows now stay compact and expose the complete context in tooltips; a long-note regression guards this behavior.
- All 113 tests pass, including 11 new comparison/model and desktop regressions. Compilation, diff checks, real-input source hash checks, normal/minimum-window visual checks, and the 0.5.0 bundle signature/smoke test pass. The previous 0.4.1 bundle is retained as a private local backup.
- No workbook, export, private annotation, generated app, or screenshot is included in the feature branch. PR creation and merge remain separate follow-up actions.
