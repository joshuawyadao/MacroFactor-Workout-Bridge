# Plan

Finish PR #5 by fixing the four remaining local-workspace review findings, preserving main's publication safeguards, and validating the combined app before the approved squash merge. Keep the separate coverage branch and all private user files unchanged.

## Scope
- In: completed-set archive validation, defensive historical metadata, relocatable archive history, custom-root Git privacy, focused regression tests, README/workflow documentation, CI, and app-branch cleanup after merge.
- Out: broader coverage-branch changes, new app features, private data edits, protection bypasses, and unrelated branch cleanup.

## Action items
[x] Inspect PR #5, main's publication changes, `docs/Local-File-Workflow.md`, and the archive tests; use an isolated checkout.
[ ] Reconcile main's README, ignore rules, and pinned CI with the existing local-workspace and calibration behavior.
[ ] Reject exports lacking any usable completed set; cover blank exercise/type, missing/nonpositive reps, and mixed-validity input in `tests/test_local_workspace.py`.
[ ] Skip malformed historical selection metadata, including invalid dates and timestamps, without losing valid history.
[ ] Resolve archived files beneath the current workspace after relocation; preserve legacy manifests and test moved/copied workspaces and unsafe paths.
[ ] Protect every managed directory under custom roots with local Git ignore rules, without replacing user ignore content; test with a real temporary Git repository.
[ ] Update `README.md` and `docs/Local-File-Workflow.md` with validation, relocation, and privacy behavior; no other public docs need behavior changes.
[ ] Run targeted tests after each fix, then the complete source-only and offscreen Qt suites, compile checks, privacy checks, and `git diff --check`; commit/push each finding separately and acknowledge its comment.
[ ] Confirm hosted CI and merge readiness, squash-merge PR #5, delete only the app feature branch, and verify the testing branch and private files are preserved.

## Open questions
- None.

## Merge gates
- Marking addressed GitHub review conversations resolved awaits the separately requested explicit permission; implementation can proceed.
