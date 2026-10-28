# Plan

Integrate the current main branch into PR #26, preserve the reviewed efficiency work and newer security pins, then complete the user-authorized merge and feature-branch cleanup.

## Scope
- In: conflict resolution against main at `37b5b50`, integration validation, refreshed PR review/CI, squash merge into main and deletion of `codex/local-efficiency` locally and remotely.
- Out: new application behavior, additional dependency upgrades, changes to other branches, private workout data and rebuilding or installing the app.

## Action items
- [x] Inspect live PR #26, merged PR #27, current refs, Development guidance and existing dependency checks; verify a clean feature worktree.
- [ ] Checkpoint this resolved plan before merging main into the feature branch.
- [ ] Merge main; retain setuptools 84.2.1 and the matching lock hash/security guidance from PR #27, retain both Brooks history records, and keep the efficiency documentation and this current plan.
- [ ] Verify all three locks match main exactly, inspect every conflict resolution, and run the canonical 513-test offscreen suite, compilation and diff checks. Existing tests cover this integration; no executable behavior or test files need changing.
- [ ] Commit and push the integration; refresh Codex review, Brooks review and CI Verify on the final feature head, checking for new comments or changes to main.
- [ ] Squash-merge PR #26 with an expected-head guard, fetch the resulting main commit, verify the efficiency implementation is present, and delete the feature branch locally and remotely.

## Open questions
- None. The user explicitly authorized merging PR #26 and deleting its feature branch. Keep main's newer dependency versions without downgrading them.

## Validation and risk
- Conflicts arise from parallel security-tooling updates and documentation/history edits; preserve both intents without changing production code.
- Main contains the same certifi 2026.10.23 and filelock 4.2.4 updates, plus newer setuptools 84.2.1. Reuse those already reviewed pins and hashes exactly.
- Prior PR #26 validation: 513 local tests passed; CI Verify and final-head Codex review passed at `3fafddb` with no findings. Recheck the integrated head before merging.
- The PR review skill readies the branch; the user's separate merge instruction authorizes the subsequent merge and cleanup.

## Change ledger
- October 28: main advanced through merged PR #27 (`37b5b50`). Read-only merge analysis found overlapping review history, Development guidance, implementation plan and app-build lock changes. Source and test files do not overlap.
