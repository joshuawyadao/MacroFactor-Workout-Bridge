# Plan

Strengthen the test suite around the bridge's safety guarantees, malformed input handling, local-workspace recovery, and desktop error-state behavior. Add focused unit and integration cases through public interfaces where practical, preserving the existing fast fixture-based suite without changing application behavior unless a test exposes a genuine defect.

## Scope
- In: workbook apply/write rejection paths, configuration and import validation, preview edge cases, workspace manifest/CLI recovery, desktop preview invalidation and failure states, test documentation, validation, commit, and push.
- Out: new product features, changing accepted file formats or mapping semantics, broad GUI automation, and coverage-percentage tooling or thresholds.

## Action items
- [x] Add reusable test helpers for temporary configuration, CSV, and XLSX mutation scenarios without introducing shared-state fixtures.
- [x] Cover configuration schema failures and MacroFactor CSV/XLSX parsing boundaries with focused unit tests.
- [x] Cover preview and workbook-apply safety gates, including stale targets, invalid output paths, empty proposals, source mutation detection, and integrity failures.
- [x] Cover local-workspace validation errors, same-day deduplication, corrupt/legacy manifests, and CLI archive/status exit behavior.
- [x] Cover desktop preview invalidation and representative discovery/preview failure states while keeping GUI tests offscreen and deterministic.
- [x] Update the README test description to reflect the strengthened negative-path coverage; no user-workflow documentation changes are expected because runtime behavior is unchanged.
- [x] Run targeted tests, both full standard and Qt suites, compile checks, and `git diff --check`; revisit any uncovered high-risk branches identified during implementation.
- [x] Commit and push the completed coverage work on the current branch.

## Open questions
- None. The recommendations will be implemented as risk-focused tests rather than an attempt to reach a numeric coverage target.

## Verification
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — 54 tests passed; three optional Qt tests skipped as expected.
- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .app-build-venv/bin/python -m unittest discover -s tests -v` — all 54 tests passed, including the three GUI tests.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
- Standard-library execution tracing confirmed the targeted risk areas improved: configuration 78%→100%, importers 81%→94%, service 79%→97%, local workspace 85%→90%, and workbook selection 86%→93%.
- No production behavior or local-file workflow changed, so `docs/Local-File-Workflow.md` required no update.
