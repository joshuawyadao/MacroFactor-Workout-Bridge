# Plan

Refresh the desktop GUI with black/charcoal surfaces, white text, clearer visual hierarchy, and easier block comparison. Preserve training metrics, source safety, and annotation workflows on `codex/block-comparison`.

## Scope
- In: shared dark theme, dashboard cards, readable tables/charts, comparison swap and context shortcuts, focus/disabled states, tests/docs, versioned app build and installation with backup, commit and push.
- Out: copied MacroFactor assets, data/model changes, recovery predictions, source-file edits, new dependencies, PR creation or merge.

## Action items
[x] Inspect desktop/comparison views, GUI tests, README, and Local-File-Workflow; retain the existing comparison feature and safety constraints.
[x] Centralize dark palette and widget styles, preserving warning contrast and clear focus/disabled/selected states.
[x] Add compact overview cards and comparison/context shortcuts without crowding the minimum-size analysis viewport.
[x] Extend GUI regressions for contrast, swap/context actions, clearing stale cards, and minimum-size rendering.
[x] Update README and Local-File-Workflow; bump release metadata consistently.
[x] Run focused/full tests, compilation, diff checks, visual inspection, and signed app build/smoke tests.
[ ] Install with recoverable backup after the user saves pending work and closes the running 0.5.0 app.
[x] Commit and push scoped files with save-branch; exclude private data and build artifacts.

## Prior milestone completion
- PR #15 merged into main as `7e3bf5b` after CI Verify passed and all three addressed review threads were resolved with user approval.
- The old feature branch was deleted locally and remotely. Version 0.4.1 and verified private week layouts were installed with recoverable backups; source workbook and export remained unchanged.

## Open questions
- None. Use a dark-only theme with restrained cyan/orange chart accents; preserve existing data semantics.

## Dark-interface verification
- Added theme contrast/calendar/popup tests and comparison regressions for swaps, context navigation, on-demand notes, stale summary clearing, sparse RIR coverage, and minimum-window rendering. The full suite contains 120 passing tests.
- Inspected Weekly Bridge, overview, comparison, context, calendar, and popup rendering at 1120×820 and 900×680. Long saved block notes moved into a read-only dialog to preserve table space. Real-input comparison retains an 82-pixel table viewport at minimum size with the existing warnings visible.
- Source workbook, export, config, and annotation hashes remained unchanged during real-input checks. No calculations, annotation schema, or input files changed.
- Compilation and diff checks pass. Version 0.5.1 (bundle build 8) is built, ad-hoc signed, signature-verified, and passes its GUI smoke test.
- Installation is pending: the user's existing 0.5.0 app is still running. Do not replace it until it is closed; retain it as `MacroFactor Workout Bridge-0.5.0-before-dark-interface.app` when installing. The built app and local screenshots remain Git-ignored/outside the repository.

## Previous comparison verification
- Source, config, and annotation hashes stayed unchanged during real-input GUI comparison checks.
- Visual inspection found the source controls crowding out comparison rows; successful loads now collapse those controls behind Show sources, and long block notes scroll inside a bounded read-only field.
- Actual Qt rendering caught a collision with QWidget's metric method; renamed the chart field and selector and retained a render regression test.
- Long real-world week notes initially expanded rows enough to obscure the comparison. Rows now stay compact and expose the complete context in tooltips; a long-note regression guards this behavior.
- All 113 tests pass, including 11 new comparison/model and desktop regressions. Compilation, diff checks, real-input source hash checks, normal/minimum-window visual checks, and the 0.5.0 bundle signature/smoke test pass. The previous 0.4.1 bundle is retained as a private local backup.
- No workbook, export, private annotation, generated app, or screenshot is included in the feature branch. PR creation and merge remain separate follow-up actions.
