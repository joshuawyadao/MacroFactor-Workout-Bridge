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
2. Create a Python 3.11 or newer virtual environment and install the desktop test dependency:

   ```sh
   python3 -m venv .venv
   .venv/bin/python -m pip install -e ".[desktop]"
   ```

3. Add or update focused tests when behavior changes. Fixtures must be synthetic or deliberately anonymized.
4. Run the complete verification gate:

   ```sh
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
   .venv/bin/python -m compileall -q src tests packaging
   git diff --check
   ```

5. Describe the user-visible behavior, privacy and workbook-safety implications, verification performed, and any manual macOS checks in the pull request.

## Design constraints

- Treat every source export and coach workbook as immutable.
- Refuse in-place output and existing output paths.
- Preserve unrelated OOXML parts and existing formulas, styles, and workbook structure.
- Prefer exact, reviewable matching over inference or fuzzy matching.
- Keep runtime processing local unless a future network feature is explicitly designed and documented.
- Keep personal data out of tests, examples, logs, screenshots, issues, and pull requests.

Report vulnerabilities using [SECURITY.md](SECURITY.md). Never publish exploit or sensitive details; if GitHub private vulnerability reporting is unavailable, a sanitized public issue may request a private contact channel. Security reports and conduct reports use separate workflows, so follow the policy that matches the concern.
