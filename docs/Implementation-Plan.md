# Plan

Isolate the shared test runner on its own feature branch and prevent concurrent worktrees from changing one another’s dependencies by keying environments to the Python version and test-lock fingerprint. Preserve automatic setup, current-worktree source imports, and the same local/CI test command.

## Scope
- In: branch isolation, fingerprint-keyed shared environments, compatibility and concurrency-focused tests, CI verification, contributor documentation, and hosted Ubuntu validation.
- Out: Maintainer-name metadata, application runtime dependencies, macOS app-build dependencies, private workout data, PR creation, and automatic deletion of the legacy shared `.venv`.

## Action items
[x] Resolve the branch split so this branch contains only test-runner changes relative to `main`.
[x] Change `scripts/test.sh` to select an immutable shared environment by Python version and `requirements/test.lock` fingerprint.
[x] Keep provisioning locks scoped to each fingerprinted environment and retain safe explicit-path overrides.
[x] Update automated tests for default environment identity, lock changes, Python versions, and explicit overrides.
[x] Reuse the existing ignored `.venv/` root and update `README.md` and `CONTRIBUTING.md` for the fingerprinted environment layout.
[x] Run targeted tests, a fresh environment bootstrap, the complete GUI-enabled suite, compilation, dependency, diff, and scope checks.
[x] Commit and push the isolated runner branch, validate it with a manual hosted workflow, and restore the spelling branch to its focused commit.

## Open questions
- None.
