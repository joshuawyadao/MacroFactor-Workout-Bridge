# Plan

Finish the dashboard rollout after PR #19 by rebuilding the merged source, validating the packaged app and existing local workspace, and replacing the local app with a recoverable backup. Close the stale review checklist using final GitHub evidence and document the repeatable local update procedure.

## Scope
- In: documentation, locked macOS build, packaged smoke/signature checks, local dashboard verification, preservation checks, local app replacement, commit and push of documentation.
- Out: dashboard feature changes, program preview/export integration, source-data or annotation corrections, version/schema changes, public binary distribution, another PR or merge.

## Action items
[x] Inspect README, docs/Local-File-Workflow.md, packaging, managed loading, existing tests and the merged PR #19 validation record.
[x] Close the previous final-validation item: PR #19 merged as 7d8a91c; its final head 4eecfb0 passed all 194 tests, CI Verify run 35261611526, compilation, smoke checks and review resolution.
[x] Build the unchanged application from merged source with scripts/build_macos_app.sh and its hash-locked dependency closure; verify the bundle signature and offscreen launch.
[x] Run existing focused dashboard/managed-loading regressions and compilation. No test files need changes because executable behavior is unchanged and the merged head already passed the complete suite.
[x] Validate automatic loading, observed coverage, block-date eligibility, charts/set inspection and feedback reopening with local data; exercise note saves on an isolated private copy and hash-check original sources/annotations.
[x] Back up the existing app, install the verified bundle at the existing local launch path, verify the installed copy and inspect its visible dashboard. Preserve saved settings and private files.
[x] Add a repeatable post-merge app-update checklist to docs/Local-File-Workflow.md; record sanitized results here without private filenames, hashes, workout details or screenshots.
[x] Review the documentation diff and privacy scope; only the plan and local-update procedure changed.
[x] Prepare the completed documentation for save-branch on the user-approved codex/dashboard-rollout-wrapup branch; commit and push are the final delivery step.

## Open questions
- None. Existing block dates and notes will be validated as supplied; unknown dates will not be inferred.

## Validation record
- PR #19: https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/pull/19
- Final pre-merge CI: https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/actions/runs/35261611526
- Before this rollout, the local bundle was version 0.9.1/build 13 and predated the final review fixes. Rebuilding retained that version; the source commit and installation verification identify this rollout.
- The locked build from 7d8a91c completed with Python 3.11; deep/strict signature verification and built/installed offscreen smoke checks passed.
- All 10 focused managed-loading, feedback, timeline and calendar-validation regressions passed. Compilation and documentation diff checks passed. The unchanged production code retains the merged head's full-suite evidence above.
- The installed bundle was compared with the new build across every file and symlink; the previous bundle was preserved and compared with its pre-update inventory. A local installation receipt records source revision and executable identity outside Git.
- Native installed-app acceptance passed: automatic loading, overview charts, timeline navigation, original-set drill-down and latest-mapped weekly feedback. Existing feedback was opened without editing, and the app was left on Overview.
- Read-only real-workspace validation and an isolated workspace-copy exercise passed: automatic startup, all lift charts, set inspection, saved-context toggle, and feedback save/reload/restart. Existing unrelated notes were preserved and every configured block passed calendar eligibility checks. The temporary workout copy was removed.
- Original-file hashes, modification times and symlink targets matched before and after validation; a follow-up integrity check also passed after native installed-app inspection.
- One pre-existing conflicting day snapshot remains visible for deliberate source review. No conflicting workouts, block dates or private annotations were modified, and no private dataset details enter this documentation change.
- The user approved the rollout documentation branch. Detailed source-conflict comparison is a separate read-only follow-up; its private results remain outside Git.
