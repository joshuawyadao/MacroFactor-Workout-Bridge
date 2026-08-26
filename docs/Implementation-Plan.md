# Plan

Keep the standalone safety and negative-path coverage expansion on a dedicated feature branch that depends on `feat/local-file-workspace`. Preserve the coverage additions independently from the app PR so they can be reviewed and merged as a focused follow-up.

## Scope
- In: reusable XLSX test helpers, configuration/import validation, preview and write safety gates, workspace recovery, desktop error states, README test documentation, validation, commit, and push.
- Out: application behavior changes, CI infrastructure, regression tests committed alongside app fixes, merging this branch, or changing its app-branch dependency.

## Action items
- [x] Preserve coverage commit `770335d` and its complete final test state on `feat/local-file-workspace-test-coverage`.
- [x] Keep the app branch free of the standalone coverage-only files and README wording.
- [x] Retain test helpers and focused unit, integration, workspace, service-edge, and desktop scenarios on this branch.
- [x] Document the strengthened negative-path coverage in the README.
- [x] Verify the complete standard and desktop-enabled suites.
- [x] Compile Python sources and check the branch diff.
- [x] Commit and push the dedicated testing branch.

## Open questions
- None. This branch remains dependent on `feat/local-file-workspace` until the app PR merges into `main`.

## Verification
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — all 59 tests passed; three optional GUI tests skipped as expected.
- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .app-build-venv/bin/python -m unittest discover -s tests -v` — all 59 tests passed, including GUI coverage.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
- Relative to the app branch before its final plan-only commits, the testing branch adds 665 lines across the intended README and six test files while leaving application and CI files unchanged.
