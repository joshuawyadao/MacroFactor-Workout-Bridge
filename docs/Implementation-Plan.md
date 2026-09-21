# Plan

Prepare the dashboard comparison-default branch for a focused pull request by rebasing it onto current `main`, preserving the GUI lifecycle fix from PR #20, and completing the repository's canonical validation gate.

## Scope
- In: branch rebase and conflict resolution, Qt test cleanup, focused and canonical validation, documentation of final evidence, commit and push, and preparation of the pull-request review evidence.
- Out: merging the pull request, rebuilding the installed app before merge, changing comparison calculations beyond the approved default-selection behavior, dependency upgrades, or modifying private workout data.

## Action items
[x] Compare the branch with current remote `main`, identify the implementation-plan and comparison-test conflicts, and diagnose the direct Qt-window cleanup finding.
[x] Rebase the two branch commits onto `origin/main` while preserving the local app-update guide, current comparison plan, PR #20's test support, and the feature tests.
[x] Replace direct cleanup for the new comparison test window with `tests.gui_support.dispose_widget`.
[x] Run the focused comparison tests, then `./scripts/test.sh` to terminal completion, the dependency audit, compilation, source smoke test, and `git diff --check`.
[x] Recheck the disposable September-export comparison and confirm private source and annotation files remain unchanged.
[x] Record the final validation and conflict resolution here and prepare the rebased branch for a force-with-lease push.
[x] Prepare a focused pull-request description with the behavior, privacy, validation, and review evidence required for the post-save PR review cycle.

## Open questions
- None. The user explicitly requested the rebase, conflict fixes, complete verification, and PR review cycle; the final merge remains theirs.

## Conflict resolution
- Rebased the two feature commits onto `origin/main` at `ebaef7e`.
- Resolved the implementation-plan conflict in favor of the current feature plan while retaining the local app-update guide from the branch.
- Preserved PR #20's shared `dispose_widget` helper and applied it to the new comparison-window regression fixture.

## Validation record
- All 16 focused comparison and GUI-lifecycle tests passed.
- The canonical `./scripts/test.sh` run passed all 200 tests in 70.924 seconds.
- The hash-locked dependency audit reported no known vulnerabilities.
- Python compilation, the source GUI smoke test, and `git diff --check` passed.
- The disposable September-export check selected an exercise with four metric-bearing weeks in each initial block. SHA-256 comparisons confirmed both source exports and the live annotation file still matched their untouched snapshots; no private data was added to Git.
