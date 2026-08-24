# Plan

Add the archive intake date to every automatically generated filename so coach and MacroFactor versions can be found by when they were uploaded. Preserve the MacroFactor workout-date range, content hash, stable current shortcuts, and non-destructive handling of original files.

## Scope
- In: upload-date-prefixed MacroFactor archive names, canonical-name migration behavior, naming tests, workflow documentation, private baseline refresh, and branch save.
- Out: renaming inbox files, changing stable `current/` shortcut names, modifying workbook contents, and changing how current versions are selected.

## Action items
- [x] Prefix MacroFactor canonical archive filenames with the UTC intake/upload date.
- [x] Keep deduplication stable and migrate legacy canonical archive entries safely without deleting older names.
- [x] Update naming tests for coach and MacroFactor files, including repeated-content behavior.
- [x] Update the README and local-file workflow guide with searchable upload-date examples.
- [x] Refresh the private baseline and verify current links, source hashes, and Git exclusions.
- [x] Run the complete standard and desktop test suites plus compile and diff checks.
- [x] Commit and push the completed change on the existing feature branch.

## Open questions
- None. “Upload date” will mean the UTC date when the archive command processes the file, formatted as `YYYY-MM-DD` at the start of every archive filename.

## Verification
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — 27 tests passed with the optional Qt GUI test skipped as expected.
- `QT_QPA_PLATFORM=offscreen .app-build-venv/bin/python -m unittest discover -s tests -v` — all 27 tests passed, including the GUI and eight local-workspace tests.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
- Private baseline refresh — both MacroFactor archive versions gained `2026-08-24` upload-date prefixes; the current link now resolves to the new searchable filename.
- Source immutability — all four inbox SHA-256 hashes matched before and after the baseline refresh.
- Privacy — `local-data/` and `config/exercises.local.json` remain Git-ignored and untracked.
