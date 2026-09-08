# Plan

Fix the observed `CI Verify` startup failure without widening the repository's GitHub Actions allowlist. Run the exact-version dependency auditor through the existing Python environment, preserve hash-enforced lock auditing, and keep the change isolated from application behavior.

## Scope
- In: CI audit execution, its dependency contract test, local audit documentation, focused validation, commit, and push.
- Out: GitHub Actions permission changes, dependency version or hash changes, application behavior, and unrelated packaging issues.

## Action items
[x] Replace the disallowed third-party audit action with an exact-version `pip-audit` install and CLI audit step.
[x] Keep the audit read-only and enforce hash validation against both complete dependency closures.
[x] Update the CI contract test to verify the package version is exact without duplicating the chosen version.
[x] Remove unnecessary local documentation coupling to one auditor release.
[x] Run focused dependency tests, workflow syntax checks, and `git diff --check`.
[x] Commit and push the CI fix, then watch the replacement `CI Verify` run to completion.

## Open questions
- None.
