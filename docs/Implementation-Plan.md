# Plan

Make the CI vulnerability-audit bootstrap reproducible by reviewing and hash-locking the complete `pip-audit` tool closure. Keep application and build dependencies unchanged while aligning CI, contributor documentation, and dependency-integrity tests with the new audit-tool lock.

## Scope
- In: a binary-only SHA-256 audit-tool lock, CI installation and cache configuration, dependency-integrity regression tests, contributor verification documentation, validation, commit, push, and PR preparation.
- Out: application runtime behavior, app-build or GUI-test dependency upgrades, advisory policy changes, macOS packaging behavior, and merging the pull request.

## Action items
[x] Resolve the complete `pip-audit==2.10.1` closure for CI's Python 3.11 Linux environment and record exact wheel hashes in `requirements/audit.lock`.
[x] Update `.github/workflows/ci-verify.yml` to cache and install the reviewed audit-tool lock with binary-only and hash verification before scanning the product locks.
[x] Extend `tests/test_build_dependencies.py` to enforce the audit lock's direct version, complete hashes, and CI installation contract.
[x] Update `CONTRIBUTING.md` and `README.md` so local verification installs the same reviewed audit tooling used by CI.
[x] Verify lock installation in an isolated environment, run the dependency audit, focused dependency tests, complete suite, source compilation, and diff checks.
[x] Review the final diff for unchanged product dependencies and document the rollback boundary as the audit lock plus its CI/docs/test wiring.
[x] Commit and push `feature/hash-lock-pip-audit`, then run the full PR review cycle without merging.

## Verification
- The 29-package lock installed from the reviewed Apple-silicon macOS wheel set, and `pip check` reported no broken requirements.
- A Python 3.11 Linux x86-64 download resolved all 29 locked packages from only the reviewed Linux wheel set with hash verification enabled.
- `pip-audit` reported no known vulnerabilities across `requirements/audit.lock`, `requirements/app-build.lock`, and `requirements/test.lock`.
- All 14 focused build-dependency tests and all 75 GUI-enabled repository tests passed.
- Source compilation and `git diff --check` passed.
- `pyproject.toml`, `requirements/app-build.lock`, and `requirements/test.lock` are unchanged. Rollback is limited to the new audit lock and its CI, documentation, test, and implementation-plan wiring.

## Open questions
- None.

## Brooks review follow-up
- [x] Remove the duplicated `pip-audit` version literal from `tests/test_build_dependencies.py` while retaining the invariant that exactly one exact `pip-audit` requirement is present in the audit lock.
- [x] Re-run the focused dependency tests and diff checks before saving the review fix.
