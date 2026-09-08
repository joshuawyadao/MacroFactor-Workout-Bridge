# Plan

Address the two actionable Brooks PR-review findings without changing the empty-day marker policy: isolate marker proposal logic from the preview transaction and directly verify the yellow desktop-table presentation. Re-run the focused and complete verification gates, then save the review fixes on the feature branch.

## Scope
- In: `build_preview` marker-policy extraction, one offscreen desktop GUI regression test, implementation-plan traceability, focused tests, full tests, compilation, and diff checks.
- Out: changing marker eligibility, workbook output behavior, exercise matching, UI layout, personal configuration or files, merging the pull request, and unrelated refactoring.

## Action items
[x] Extract empty-day marker proposal logic from `build_preview` into a focused private helper in `service.py`.
[x] Preserve the current conservative eligibility checks, proposal ordering, report metadata, and configured marker color.
[x] Add an offscreen GUI test proving highlighted proposals render with the configured yellow background and review text.
[x] Run the focused service/integration and desktop GUI tests.
[x] Run the complete repository test suite, source compilation, and diff checks.
[x] Mark this plan complete, commit the review fixes, and push the feature branch.

## Open questions
- None.
