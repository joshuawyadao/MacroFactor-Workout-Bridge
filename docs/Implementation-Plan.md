# Plan

Refresh only the vulnerable audit and build dependencies, verify their complete hash-pinned closures on Python 3.11, and prepare a reviewed pull request with a rebuilt, smoke-tested macOS app.

## Scope
- In: `certifi` 2026.7.22 → 2026.10.23 and `filelock` 3.32.6 → 4.2.4 in `requirements/audit.lock`; `setuptools` 84.0.0 → 84.2.1 in `requirements/app-build.lock`; canonical dependency notes in `docs/Development.md`; local and hosted verification; PR review ledger.
- Out: PySide6, Shiboken, PyInstaller, Python minor-version migrations, application behavior, personal data, system Python, installed Applications bundles, and merging the PR.

## Action items
- [x] Inspect the README, Development guide, all three locks, `pyproject.toml`, build/test scripts, CI and `tests/test_build_dependencies.py`; refresh `origin/main` and current advisory evidence.
- [x] Commit this resolved plan on `codex/dependency-security-refresh` before implementation (`fbbb735`).
- [x] Verify target wheel SHA-256 values against PyPI and refresh only the affected exact pins/hashes, keeping the rest of each complete closure fixed.
- [x] Validate the filelock major upgrade against CacheControl's actual file-cache API and Python 3.11 requirements; use an isolated audit environment, dependency resolution, `pip check`, and repeated cached audits. Existing dependency tests and real consumer checks cover this configuration-only change, so no new test files are planned.
- [x] Update `docs/Development.md` with the security rationale and the audit-only filelock compatibility boundary; retain binary-only and required-hash installation instructions.
- [x] Resolve/install audit and app-build closures on patched Python 3.11.17, validate Linux x86-64 audit wheels, audit all three locks, and run the existing focused dependency tests plus the full offscreen GUI suite, compilation and diff checks.
- [x] Rebuild the macOS app, verify the ad-hoc signature, run its embedded-runtime smoke check, and confirm the bundled Python version. Each lock closure is an independent rollback boundary; do not roll back to vulnerable versions for routine continued use.
- [ ] Save and push the branch, open a PR against `main`, request Codex review, run Brooks review, and address actionable review/CI failures until merge-ready; record concrete results below.

## Open questions
- None. Current PyPI metadata confirms the three targets are available and have no reported advisories. All three current vulnerable versions are reported by PyPI; leaving filelock unchanged would fail the existing all-lock CI audit. CacheControl requires `filelock>=3.8.0` with no major upper bound; the upgrade remains confined to audit tooling and must pass its real cache path before acceptance.

## Validation results

- Audited all 37 unique exact locked packages against current PyPI advisory data; only certifi, filelock and setuptools required changes. Target universal-wheel SHA-256 values matched PyPI; pip accepted the complete unchanged remainder of each closure with required hashes.
- Provisioned an isolated Python 3.11.17 / OpenSSL 3.5.9 runtime from the checksum-verified python-build-standalone 20261013 archive; the system interpreter and installed app were not modified.
- Audit environment: full dependency resolution and `pip check` passed. CacheControl 0.14.4 with filelock 4.2.4 passed cache miss/read/write/replace/delete, separate-body cache, 40 concurrent distinct-key writes and 40 same-key writes. All-lock `pip_audit --disable-pip --require-hashes` passed twice with the same explicit cache directory, reporting no known vulnerabilities each time.
- Linux x86-64 Python 3.11 audit closure downloaded successfully with binary-only wheels and required hashes.
- Existing dependency/documentation tests: 20 passed in 8.831 seconds, exit 0. No test files changed because application behavior and desktop dependencies are unchanged; real cache-consumer and build checks exercise the updated third-party integration.
- macOS app rebuilt and ad-hoc signature verification passed; embedded GUI smoke passed. Bundled `libpython3.11.dylib` reports Python 3.11.17. Build environment `pip check` passed with setuptools 84.2.1. Compilation and `git diff --check` passed.
- Complete offscreen suite: 496 tests passed in 62.765 seconds, no skips, exit 0. Hosted CI and PR reviews remain pending.

## PR review ledger

- Plan checkpoint: `fbbb735`; isolated audit-tool upgrade checkpoint: `782edae`. Build tooling and canonical dependency notes are saved separately so the two lock updates remain independently reviewable.
- Independent workbook-integrity review: no actionable findings; application source, test files, desktop pins, packaging scripts and CI are unchanged. Remaining gates are hosted CI and PR reviews.
- The old GitHub CI/comment helper skill paths referenced by the PR workflow are not installed. Use native GitHub CLI/API check diagnostics and thread-aware GraphQL reads if needed; this does not change the review or verification gates.
