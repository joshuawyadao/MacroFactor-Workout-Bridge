# Plan

Make the pending MacroFactor CI workflow quota-aware before it reaches `main`. Preserve its complete Linux verification while running it only for merge-ready pull requests or manual requests, cancelling superseded work, and avoiding a duplicate post-merge run.

## Scope
- In: `.github/workflows/ci-verify.yml` trigger, concurrency, draft policy, manual dispatch, and README CI guidance on the existing PR branch.
- Out: application behavior, Python tests, packaging behavior, branch-protection settings, paid or self-hosted runners, and the local-only `local-data/` directory.

## Action items
[x] Restrict hosted CI to merge-ready pull requests plus manual dispatch, removing the duplicate `main` push trigger.
[x] Add per-workflow/per-ref concurrency cancellation while preserving the existing timeout, permissions, test suite, compile check, and pull-request diff check.
[x] Document the hosted CI trigger and manual-dispatch policy in the README.
[x] Validate YAML parsing, workflow-policy invariants, `git diff --check`, and the scoped diff; no Python test files are needed because executable bridge behavior is unchanged.
[x] Commit and push the existing `feat/local-file-workspace` PR branch while leaving `local-data/` in the original checkout untouched.

## Open questions
- None.
