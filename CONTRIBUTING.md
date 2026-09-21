# Contributing

Thanks for taking the time to improve MacroFactor Workout Bridge.

## Code of conduct

By participating, you agree to follow the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). Report conduct concerns privately using the email channel in that policy; do not post reports or sensitive personal details in a public issue.

## Before opening a change

1. Search existing issues and pull requests to avoid duplicate work.
2. Open an issue first for changes that alter source-file immutability, overwrite protection, workbook-part preservation, exercise matching, privacy behavior, or external data access.
3. Keep pull requests focused on one coherent outcome.
4. Never commit real MacroFactor exports, coach workbooks, generated reports, local manifests, credentials, or machine-specific paths.

## Development workflow

1. Fork the repository and create a descriptive branch from `main`.
2. Run the canonical test command from any linked worktree:

   ```sh
   ./scripts/test.sh
   ```

   The first run provisions the pinned desktop test dependencies under the primary checkout's ignored `.venv/worktree-tests/` directory. Environments are keyed by Python version and test-lock fingerprint, so compatible worktrees reuse dependencies without allowing divergent branches to modify one another's environment.

   Follow the command until the process exits. The offscreen GUI suite can take several minutes; a short command-output window is not a test timeout. If your terminal or automation tool returns a running session, continue collecting that session's output instead of starting another copy of the suite. Record the final `Ran ... tests in ...s` summary, `OK` or failure result, skipped-test count, and exit status in the PR. A partial list of passing cases is not a complete result. Do not claim GUI coverage from a source-only `python -m unittest` run that skips tests because PySide6 is unavailable.

3. Add or update focused tests when behavior changes. Fixtures must be synthetic or deliberately anonymized.

   GUI fixtures should register `self.addCleanup(dispose_widget, widget)` from `tests.gui_support` immediately after creating a top-level widget, inside the existing optional-Qt import guard. Register temporary-directory cleanup first so the widget and its workers finish before fixture files are removed. The helper closes the widget, waits for background jobs, and processes Qt's deferred deletion; `close()` alone can retain hidden widgets and make later application-wide styling progressively slower.

4. Run the complete verification gate:

   ```sh
   ./scripts/test.sh
   python3.11 -m venv --clear .venv/audit
   .venv/audit/bin/python -m pip install \
     --only-binary=:all: \
     --require-hashes \
     --requirement requirements/audit.lock
   .venv/audit/bin/python -m pip_audit --disable-pip --require-hashes \
     --requirement requirements/audit.lock \
     --requirement requirements/app-build.lock \
     --requirement requirements/test.lock
   python3 -m compileall -q src tests packaging
   git diff --check
   ```

   The dependency audit requires Python 3.11 because the lock contains the exact Linux and macOS wheels reviewed for that interpreter. It installs `pip-audit` and its complete transitive closure from `requirements/audit.lock`, using the same exact versions and wheel hashes as CI. Dependency lock changes must retain exact versions, reviewed wheel SHA-256 hashes, and binary-only installation unless a separately reviewed source-build requirement is documented.

5. Describe the user-visible behavior, privacy and workbook-safety implications, verification performed, and any manual macOS checks in the pull request.

## Design constraints

- Treat every source export and coach workbook as immutable.
- Refuse in-place output and existing output paths.
- Preserve unrelated OOXML parts and existing formulas, styles, and workbook structure.
- Prefer exact, reviewable matching over inference or fuzzy matching.
- Keep runtime processing local unless a future network feature is explicitly designed and documented.
- Keep personal data out of tests, examples, logs, screenshots, issues, and pull requests.

Report vulnerabilities using [SECURITY.md](SECURITY.md). Never publish exploit or sensitive details; if GitHub private vulnerability reporting is unavailable, a sanitized public issue may request a private contact channel. Security reports and conduct reports use separate workflows, so follow the policy that matches the concern.
