# Plan

Make Compare blocks open with a useful exercise for its initial A/B block pair instead of the alphabetically first exercise when that exercise has no data there. Rank initial candidates by coverage in both selected blocks and availability for the selected chart metric, while preserving a user's explicit exercise selection across reloads.

## Scope
- In: initial Compare blocks exercise selection, deterministic fallback behavior, focused GUI regression coverage, comparison documentation, validation, commit, and push on the current branch.
- Out: changing comparison calculations, combining exercise variations, automatically replacing an exercise after the user changes a selector, modifying workout sources or annotations, or opening another pull request.

## Action items
[x] Add deterministic initial-exercise selection to `src/macrofactor_bridge/comparison_view.py` using the default or restored A/B blocks and existing weekly trends.
[x] Preserve valid explicit exercise selections on reload and fall back safely when the selected blocks have no jointly logged exercise.
[x] Extend `tests/test_comparison_gui.py` with a regression where the alphabetically first exercise has no selected-block data and confirm explicit selections remain stable.
[x] Update `README.md` and `docs/Local-File-Workflow.md` to describe the comparison's useful-data default and selection-preservation behavior.
[x] Run the focused comparison tests, the relevant dashboard/managed-history GUI suite, and compilation checks.
[x] Exercise Compare blocks against the disposable copy of the latest weekly exports and confirm the initial table/chart contain logged data without changing private sources or annotations.
[x] Review the diff and privacy scope and prepare only the requested files for commit and push on `codex/dashboard-rollout-wrapup`.

## Open questions
- None.

## Validation record
- All 12 focused comparison GUI tests passed, including the two new default-selection and selection-preservation regressions.
- All 62 comparison, timeline, managed-history, and managed-GUI tests passed after the production change.
- Python compilation and `git diff --check` passed.
- The disposable copy of the September weekly exports opened Compare blocks with one exercise containing logged weeks and estimated-1RM values in both initial blocks. No private input or annotation file was added to Git.
