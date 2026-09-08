# Plan

Integrate current `main` into the dependency-integrity branch without losing either change. Preserve `main`'s override-safe GUI runner test and this branch's hash-enforced dependency installation and allowlist-compatible advisory audit.

## Scope
- In: `docs/Implementation-Plan.md` conflict resolution, verification of the shared test change, dependency contracts, complete GUI suite, merge commit, and CI rerun.
- Out: GitHub Actions permission changes, dependency version or hash changes, application behavior, and unrelated packaging issues.

## Action items
[x] Capture the isolated GUI-suite failure and confirm it is limited to the default-root assertion inheriting `MACROFACTOR_TEST_VENV_ROOT`.
[x] Update the default-root test to remove the override from the subprocess environment without weakening its path and fingerprint assertions.
[x] Preserve the allowlist-compatible `pip-audit` CLI gate and binary-only SHA-256 lock enforcement from the feature branch.
[x] Run the focused dependency tests and complete GUI-enabled suite after the merge.
[x] Run source compilation, shell syntax, dependency audit, and diff checks.
[x] Commit and push the conflict resolution, then watch fresh CI and Codex review gates.

## Open questions
- None.
