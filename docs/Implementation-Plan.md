# Plan

Add a private local workspace where recurring MacroFactor exports and coach workbooks can be dropped, validated, and copied into a dated, hash-addressed history. Personal inputs, manifests, and generated workbooks will stay outside Git, while a reusable setup/archive command and documentation make the workflow repeatable.

## Scope

- In: ignored intake/archive/output directories, non-destructive input validation, content-hash version names, JSON manifests, latest-version status, automated tests, and user documentation.
- Out: committing personal files, deleting or moving inbox files, cloud backup, live MacroFactor synchronization, automatically modifying coach workbooks, and changing the completed MVP branch.

## Action items

- [x] Add a local-workspace module and command that creates the standard private directory structure.
- [x] Validate coach `.xlsx` files and MacroFactor `.csv`/`.xlsx` exports before archiving them.
- [x] Copy valid inputs into immutable-style dated/hash-named archive paths without overwriting or removing inbox files.
- [x] Write a manifest for each intake run with hashes, source metadata, validation summaries, and archive locations.
- [x] Add status output that identifies the newest archived coach workbook and MacroFactor export for the desktop workflow.
- [x] Exclude the entire local workspace from Git and initialize the requested folders locally.
- [x] Add automated tests for setup, validation, archival, deduplication, manifests, and source immutability.
- [x] Document the recurring drop, archive, preview, and generated-output workflow in the README and a focused guide.
- [x] Run the complete test suite, update this plan with verification results, and commit and push the new feature branch.

## Open questions

- None. The workflow will default to `local-data/`, copy rather than move inputs, and use local manifests as validation history rather than placing personal files in Git.

## Verification

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — 23 tests passed; the optional Qt GUI test skipped as intended without desktop dependencies.
- `QT_QPA_PLATFORM=offscreen .app-build-venv/bin/python -m unittest discover -s tests -v` — all 24 tests passed, including the GUI workflow and five new local-workspace tests.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
- Local baseline intake — the existing coach workbook plus XLSX and all-time CSV exercise logs were copied from Downloads, validated, archived with SHA-256 names, and recorded in a zero-error manifest.
- Privacy verification — `local-data/` and `config/exercises.local.json` are ignored by Git; no personal input, archive, manifest, report, or generated workbook is staged.
