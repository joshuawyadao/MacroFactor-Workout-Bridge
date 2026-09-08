# Plan

Address the Brooks review finding without changing the selected audit action or dependency behavior. Preserve the security invariant that the GitHub Action is pinned to an immutable commit while removing the test's duplicate copy of that commit SHA.

## Scope
- In: the CI audit-action pin contract, its focused test, Brooks review history, validation, commit, and push.
- Out: changing the selected action version, dependency versions or hashes, application behavior, and unrelated packaging issues.

## Action items
[x] Replace the duplicated audit-action SHA assertion with a structural immutable-commit assertion in `tests/test_build_dependencies.py`.
[x] Preserve coverage for exactly one configured audit action and its required inputs and hash-checking settings.
[x] Record the Brooks PR Review result and score in the project review history.
[x] Run the focused dependency test module and `git diff --check`.
[x] Commit the focused Brooks remedy and updated implementation plan.
[x] Push `codex/dependency-integrity-audit` and re-check PR review, CI, and mergeability state.

## Open questions
- None.
