# Plan

Harden pull request #14 before merge by preventing private annotations from being saved against stale History inputs and by splitting the new history aggregation pipeline into named, typed stages. Preserve the milestone's calculations, UI, privacy boundaries, and source-file immutability while adding focused regression protection.

## Scope
- In: History-source invalidation in the desktop workflow, typed aggregation state and extracted analysis helpers in `history.py`, regression tests, the complete test suite, and a focused review-fix commit on `codex/workout-dashboard-mvp`.
- Out: new dashboard metrics, visual redesign, recovery or deload prediction, source-file writes, annotation schema changes, and unrelated cleanup in the existing Weekly Bridge workflow.

## Action items
[x] Add an offscreen GUI regression test proving that changing any History input clears the loaded dashboard and disables annotation saving.
[x] Connect History source, mapping, and annotation path changes to a single invalidation boundary without disrupting fields while the dashboard is loading.
[x] Replace the untyped weekly aggregation dictionary with an explicit accumulator and extract block counting, date mapping, trend construction, duration summarization, and final block-summary stages from `build_history_dashboard`.
[x] Verify the refactor preserves existing calendar-week, block mapping, estimated-1RM, RIR, duration, warning, and annotation behavior through the focused History and GUI tests.
[x] Record that no README or other durable user documentation changes are required because this fixes stale UI state and internal structure without changing the documented workflow or data format.
[x] Run the complete `./scripts/test.sh` suite, source compilation, `git diff --check`, and source GUI smoke test.
[x] Commit and push only the review-remediation files; keep private data and ignored build artifacts out of Git.

## Open questions
- None.
