# Plan

Resolve the Brooks PR-review finding that an unusable coach workbook can be archived and promoted as the current validated workbook. Make coach discovery a hard validation boundary, add a regression test, and verify the complete workflow before saving the review fix.

## Scope
- In: coach-workbook archive validation, manifest error behavior, current-link protection, regression coverage, verification, commit, and push.
- Out: changing MacroFactor export validation, exercise matching rules, archive naming, or current-version selection among valid files.

## Action items
- [x] Change `local_workspace._validate_coach` to reject workbooks with no configured exercise header and week labels.
- [x] Preserve the existing validation metadata shape for usable coach workbooks.
- [x] Add a regression test proving an unusable `.xlsx` remains in the inbox, is recorded as an error, and is not archived or promoted to `current`.
- [x] Confirm the existing successful coach-workbook archive and mixed-validity tests still pass.
- [x] Run targeted tests, both complete standard and Qt suites, compile checks, and `git diff --check`.
- [x] Commit and push the Brooks review fix to the current PR branch.

## Open questions
- None. A coach workbook is valid for archival only when the app can discover at least one configured exercise header and week on the same workbook.

## Verification
- `PYTHONPATH=src python3 -m unittest tests.test_local_workspace -v` — all 13 local-workspace tests passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — 55 tests passed; three optional Qt tests skipped as expected.
- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .app-build-venv/bin/python -m unittest discover -s tests -v` — all 55 tests passed, including the three GUI tests.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
- `README.md` and `docs/Local-File-Workflow.md` already state that invalid files are not archived, so the code fix restores documented behavior without further documentation changes.
