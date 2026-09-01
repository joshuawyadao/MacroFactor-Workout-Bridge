# Plan

Address all four actionable Codex review threads on PR #7 while preserving the canonical test command and fingerprinted environment layout. Handle each concern as an independently validated commit, push, and acknowledgment, then leave the pull request open for maintainer review.

## Scope
- In: owner-aware provisioning locks, incomplete-environment recovery, isolated `PYTHONPATH`, signal-safe lock cleanup, regression coverage, CI, and Codex comment acknowledgment.
- Out: dependency-version changes, application behavior, maintainer-name changes, resolving GitHub threads, explanatory GitHub replies, and merging PR #7.

## Action items
[x] Replace the fixed 30-second wait with an atomic owner-aware lock that waits while provisioning is alive and safely recovers stale locks.
[x] Recreate any not-ready fingerprinted environment before installing dependencies so interrupted virtual environments recover automatically.
[x] Set `PYTHONPATH` exclusively to the launching worktree's `src/` directory so caller dependencies cannot affect readiness or GUI tests.
[ ] Make `HUP`, `INT`, and `TERM` handlers release only the current runner's lock and exit with the conventional signal status.
[ ] Add focused regression coverage for lock ownership, stale locks, incomplete environments, inherited path isolation, and provisioning signals.
[ ] Validate each feedback item before its separate commit, push, and thumbs-up reaction; then run the complete GUI-enabled suite, compilation, dependency, shell, and diff checks.
[ ] Re-read PR #7 threads, CI, and mergeability, leaving the PR open and unmerged for maintainer review.

## Open questions
- None.
