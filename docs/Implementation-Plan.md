# Plan

Add a friendly, double-clickable macOS application around the completed MacroFactor-to-coach-workbook engine. The app will guide the user through file selection, worksheet and week selection, review, and safe workbook creation without requiring terminal prompts, while keeping the existing command-line workflow available.

## Scope

- In: a native-style PySide6 desktop interface, file pickers, worksheet/week discovery, calendar dates, a proposed-change table, review-needed reporting, safe output selection, a bundled editable mapping example, a reproducible PyInstaller `.app` build, local ad-hoc signing, automated tests, and updated documentation.
- Out: the reverse coach-program import workflow, automatic fuzzy exercise matching, edits to original workout files, Apple Developer ID signing/notarization, App Store distribution, Windows/Linux installers, and changes to `main`.

## Action items

- [x] Record the approved desktop tracer-bullet in GitHub issue [#4](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/issues/4).
- [x] Add a framework-independent desktop workflow model for defaults, resource discovery, output naming, and human-readable safety reports.
- [x] Build the graphical workflow for choosing inputs, selecting the target worksheet/week, previewing changes, reviewing skipped data, and creating a separate workbook.
- [x] Bundle a default exercise mapping and let users save an editable copy without changing the application bundle.
- [x] Add a reproducible macOS packaging script and PyInstaller specification that creates an ad-hoc-signed `MacroFactor Workout Bridge.app`.
- [x] Add automated tests for desktop workflow helpers and a packaged-app smoke-test mode while retaining all existing CLI and workbook tests.
- [x] Update the README with graphical installation, usage, safety, build, Gatekeeper, and known-limitation guidance.
- [x] Build the local `.app`; run unit, integration, workbook-integrity, GUI smoke, bundle metadata, and code-signature checks.
- [x] Mark this plan complete and commit and push the finished feature branch for review without modifying `main`.

## Open questions

- None. This build targets the current Apple-silicon Mac, uses a self-contained Qt runtime, and applies an ad-hoc local signature; public distribution signing and notarization remain future work.

## Verification

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — 18 tests passed; the optional Qt GUI test skipped as intended without desktop dependencies.
- `QT_QPA_PLATFORM=offscreen .app-build-venv/bin/python -m unittest discover -s tests -v` — all 19 tests passed, including the populated graphical preview.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
- `./scripts/build_macos_app.sh` — created the 75 MB Apple-silicon `dist/MacroFactor Workout Bridge.app`, generated its icon, ad-hoc signed it, and verified the deep signature.
- Packaged executable `--smoke-test` — passed using the embedded Qt runtime and bundled mapping.
- Bundle checks — identifier, version `0.2.0`, macOS 13 minimum, icon, arm64 executable, and ad-hoc signature all confirmed.
- Visual GUI inspection — anonymized Week 1 preview showed all six proposed writes and all five conservative review categories in the two-panel layout.
- Workbook integration validation — the anonymized apply test created six writes while preserving source/export hashes, formulas, styles, merged cells, ZIP membership, and byte-identical unrelated workbook parts.
