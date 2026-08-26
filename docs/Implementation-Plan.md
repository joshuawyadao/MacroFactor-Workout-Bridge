# Plan

Add the missing GitHub Actions verification gate required to shepherd PR #5 to merge-ready. Mirror the repository's documented desktop-capable test command in a deterministic pull-request workflow, then validate and save the workflow without changing application behavior.

## Scope
- In: a `CI Verify` GitHub Actions workflow, Python 3.11 setup, desktop-extra installation, headless full-suite execution, compile validation, diff checking, commit, and push.
- Out: deployment, app packaging/signing, release automation, coverage thresholds, and branch-protection policy changes.

## Action items
- [x] Add `.github/workflows/ci-verify.yml` for pull requests and pushes to `main`.
- [x] Install the project with its desktop extra so the three PySide6 GUI tests run rather than skip.
- [x] Run all unit/integration/GUI tests headlessly and compile `src`, `tests`, and `packaging`.
- [x] Install Ubuntu's `libegl1` runtime required for PySide6 to import in the headless runner.
- [x] Check the pull-request diff for whitespace errors with full checkout history available.
- [x] Validate the workflow structure plus the complete local standard and Qt suites.
- [x] Commit and push the CI workflow to PR #5, then wait for `CI Verify` to reach a terminal passing state.

## Open questions
- None. CI will verify the supported Python 3.11 baseline on Ubuntu; macOS app packaging remains covered by the existing local build workflow rather than this PR gate.

## Verification
- Ruby's YAML parser accepted `.github/workflows/ci-verify.yml`; `actionlint` is not installed locally, so GitHub Actions will provide the authoritative workflow validation.
- The first GitHub run reached the full suite but failed importing PySide6 because `libEGL.so.1` was absent; the workflow now installs the providing `libegl1` package before running tests.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — 55 tests passed; three optional Qt tests skipped as expected.
- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .app-build-venv/bin/python -m unittest discover -s tests -v` — all 55 tests passed, including the three GUI tests.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
- The workflow uses read-only repository permissions, a ten-minute timeout, full history for the PR diff check, and no deployment or secret access.
