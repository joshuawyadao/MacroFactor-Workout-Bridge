# Plan

Make PR #5's macOS app build reproducible and auditable by pinning the tested PySide6 and PyInstaller dependency closure, while retaining the project's Python 3.11 support and existing runtime-dependency-free CLI. The change deliberately avoids a framework major migration or runtime dependency expansion.

## Scope
- In: exact app-build dependency lock, direct optional-dependency pins, deterministic build installation, build/verification documentation, and dependency-focused validation.
- Out: application feature changes, PySide6/PyInstaller major upgrades, runtime dependencies, CI toolchain upgrades, and unrelated PR #5 work.

## Action items
[x] Inspect PR #5's manifest, packaging script, CI, documentation, and current dependency-audit evidence.
[x] Resolve the direct app-build dependencies against Python 3.11 and record their exact compatible transitive closure.
[x] Add the reviewed app-build lockfile and pin the direct optional dependencies in `pyproject.toml`.
[x] Update `scripts/build_macos_app.sh` to install only the lockfile before installing the local project without dependency resolution.
[x] Document the reproducible build dependency policy and exact update/validation workflow in `README.md`.
[x] Verify the lockfile in a clean temporary virtual environment with `pip check`, then run the complete offscreen test suite, compile checks, and `git diff --check`.
[x] Review the final diff, commit the scoped files, and push the commit to PR #5's remote branch.

## Open questions
- None.
