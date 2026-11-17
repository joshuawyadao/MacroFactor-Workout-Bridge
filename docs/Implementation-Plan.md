# Plan

Run MacroFactor's complete portable and packaged-app verification after main merges while preserving existing PR/manual behavior and required fail-closed CI.

## Scope
- In: Main-push workflow trigger, explicit eligible-event job conditions, event-matrix regression coverage, canonical Development documentation and PR review.
- Out: Product behavior, dependencies/toolchain pins, Actions permissions/policy, real workbooks, signing/distribution and merging the PR.

## Action items
- [x] Inspect README, Development, workflow, required platform aggregate and existing build-dependency tests on main fbeb550.
- [x] Reproduce missing main-push execution with focused workflow/event regression tests before the fix.
- [x] Enable pushes only to main; run portable, packaged ARM and aggregate for main pushes, ready PRs and manual dispatch, preserving draft/unknown-event refusal.
- [x] Preserve exact Python/uv/hash provisioning, permissions and literal-success aggregate requirements; extend existing failure/skip/cancellation assertions only where needed.
- [x] Update docs/Development.md with PR and post-merge behavior and actual verification limits.
- [ ] Run focused stdlib tests, shell/whitespace checks, then hosted full portable and actual packaged macOS validation.
- [ ] Save/push, open a PR, obtain exact-head Codex and Brooks reviews, address findings and confirm required CI Verify plus clean mergeability; leave unmerged.

## Open questions
None.

Validation before save: the new main-push eligibility regression failed against the original missing trigger, then passed after the workflow correction. All23 build-dependency cases and the focused real shell aggregate cases pass; diff whitespace is clean. Local interpreter3.11.2 and missing PySide6 do not meet packaged/native requirements, so full Python/Qt and actual ARM app smoke remain hosted PR gates. Main-push execution itself becomes observable after merging; this PR is left unmerged.
