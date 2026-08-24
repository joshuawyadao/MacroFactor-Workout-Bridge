# Plan

Make uploaded filenames irrelevant to the recurring workflow. Derive readable archive names from validated file content, retain each original filename in its manifest, and maintain stable “Current” shortcuts so the desktop app always has an obvious coach workbook and MacroFactor export to open.

## Scope

- In: content-derived archive names, stable current-file shortcuts, collision-safe updates, manifest metadata, status output, automated tests, documentation, and migration of the existing local baseline through the updated intake command.
- Out: renaming or deleting uploaded inbox files, modifying personal workbook contents, cloud synchronization, and choosing an exercise mapping automatically.

## Action items

- [x] Generate canonical coach and MacroFactor archive names without relying on the uploaded filename.
- [x] Add stable `current/` shortcuts that safely follow the newest validated coach workbook and workout export.
- [x] Preserve original upload names and modification timestamps in each manifest and expose the selected current files in status output.
- [x] Add tests for arbitrary input names, date-derived naming, shortcut updates, deduplication, and overwrite protection.
- [x] Update the README and local-file workflow guide so no manual renaming is required.
- [x] Run the updated intake over the private baseline, verify source immutability and Git exclusion, then run the full test and workbook-validation suite.
- [x] Commit and push the completed changes on the existing feature branch.

## Open questions

- None. Coach archives will use the intake date, MacroFactor archives will use their validated workout-date range, and stable current shortcuts will be managed only when they are symbolic links created by this tool.

## Verification

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — 26 tests passed with the optional Qt GUI test skipped as expected.
- `QT_QPA_PLATFORM=offscreen .app-build-venv/bin/python -m unittest discover -s tests -v` — all 26 tests passed, including the GUI and seven local-workspace tests.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
- Private baseline intake — two coach workbooks and two MacroFactor exports validated with no intake errors; canonical archive entries and both stable current links were created.
- Source immutability — all four inbox SHA-256 hashes matched their pre-intake values; the current links resolve to the selected archive copies with matching hashes.
- Privacy — `local-data/` and `config/exercises.local.json` remain Git-ignored and untracked.
