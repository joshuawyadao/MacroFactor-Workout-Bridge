# Plan

Refresh only the vulnerable audit and build dependencies, verify their complete hash-pinned closures on Python 3.11, and prepare a reviewed pull request with a rebuilt, smoke-tested macOS app.

## Scope
- In: `certifi` 2026.7.22 → 2026.10.23 and `filelock` 3.32.6 → 4.2.4 in `requirements/audit.lock`; `setuptools` 84.0.0 → 84.2.1 in `requirements/app-build.lock`; canonical dependency notes in `docs/Development.md`; local and hosted verification; PR review ledger.
- Out: PySide6, Shiboken, PyInstaller, Python minor-version migrations, application behavior, personal data, system Python, installed Applications bundles, and merging the PR.

## Action items
- [x] Inspect the README, Development guide, all three locks, `pyproject.toml`, build/test scripts, CI and `tests/test_build_dependencies.py`; refresh `origin/main` and current advisory evidence.
- [ ] Commit this resolved plan on `codex/dependency-security-refresh` before implementation.
- [ ] Verify target wheel SHA-256 values against PyPI and refresh only the affected exact pins/hashes, keeping the rest of each complete closure fixed.
- [ ] Validate the filelock major upgrade against CacheControl's actual file-cache API and Python 3.11 requirements; use an isolated audit environment, dependency resolution, `pip check`, and repeated cached audits. Existing dependency tests and real consumer checks cover this configuration-only change, so no new test files are planned.
- [ ] Update `docs/Development.md` with the security rationale and the audit-only filelock compatibility boundary; retain binary-only and required-hash installation instructions.
- [ ] Resolve/install audit and app-build closures on patched Python 3.11.17, validate Linux x86-64 audit wheels, audit all three locks, and run the existing focused dependency tests plus the full offscreen GUI suite, compilation and diff checks.
- [ ] Rebuild the macOS app, verify the ad-hoc signature, run its embedded-runtime smoke check, and confirm the bundled Python version. Each lock closure is an independent rollback boundary; do not roll back to vulnerable versions for routine continued use.
- [ ] Save and push the branch, open a PR against `main`, request Codex review, run Brooks review, and address actionable review/CI failures until merge-ready; record concrete results below.

## Open questions
- None. Current PyPI metadata confirms the three targets are available and have no reported advisories. All three current vulnerable versions are reported by PyPI; leaving filelock unchanged would fail the existing all-lock CI audit. CacheControl requires `filelock>=3.8.0` with no major upper bound; the upgrade remains confined to audit tooling and must pass its real cache path before acceptance.
