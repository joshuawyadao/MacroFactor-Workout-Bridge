# Plan

Correct history mapping for coach sheets containing copied historical columns and date-labelled training weeks. Store an explicit, validated week layout in private annotations so the dashboard counts and dates only the selected weeks.

## Scope
- In: ordered history week layouts, source-header validation, consistent calendar mapping and counts, desktop save preservation, synthetic tests, documentation, real-data verification and backups, app rebuild, and PR preparation.
- Out: inferred injury labels, source workbook edits, Weekly Bridge changes, automatic date guessing, and milestone-two comparisons.

## Action items
[x] Add typed ordered week-layout entries with labels and verified source anchors; read legacy annotations and prevent older apps dropping layout data.
[x] Resolve layouts once for counts, date ranges, summaries, and desktop week selection; reject stale headers, duplicate columns, invalid anchors, and missing configured blocks.
[x] Cover copied columns, date-labelled weeks, multi-row merged headers (found during real-data validation), missing workouts, calendar boundaries, legacy files, invalid layouts, and desktop save/reload preservation.
[x] Update README and Local-File-Workflow with configuration, compatibility, calendar semantics, and correction steps.
[x] Verify the real irregular block with its confirmed three-week range; preserve sources and existing context with before/after backups.
[x] Run the complete suite, compilation, diff checks, and rebuilt app smoke verification (102 tests passed after review fixes; signed 0.4.1 bundle smoke-tested with the previous app retained).
[ ] Commit and push the feature branch; shepherd the PR through reviews and CI without merging.
[x] Address Codex P2: distinguish single-column vertical merges from unmerged headers; added a regression, validated 11 layout tests, and saved/reacted (`bf019d3`, comment 4019341775).
[x] Address Codex P2: reject result columns overlapping another selected header span; added an order-independent regression, validated 12 layout tests, and saved/reacted (`593cf93`, comment 4019341785).
[x] Address Codex P2: reject shared-formula headers even with empty formula text; preserve formula presence in OOXML snapshots, add cached/uncached regressions, validate all 102 tests, and save/react (`c33419a`, comment 4019341799).

## Validation and review ledger
- Final compatibility inspection found that sorting by label position could reorder repeated legacy labels. Preserved original discovery order when the numeric-label helper declines sorting; the new regression and full 99-test suite pass. Real-data desktop loading still verifies.
- Real-input validation exposed two-row merged headers; adjusted validation and the synthetic fixture before publication. Both source hashes stayed unchanged.
- Packaging smoke verification exposed a stale bundle version; aligned package, runtime, and bundle metadata at 0.4.1.
- Private layout saved only after the compatible app was installed, with verified before/after backups and all unrelated context preserved.
- Implementation saved in `4a8846c` on `codex/history-week-layout`; PR #15 opened for review.
- Brooks PR review: sampled the highest-risk changes, no actionable decay findings at that pass (100/100; prior run 90). Layout policy stays isolated from Weekly Bridge discovery, and tests cover boundary and persistence behavior. The subsequent compatibility inspection found and fixed the legacy-order edge case above (`ab7a800`).
- Codex review completed with three P2 findings, all fixed and acknowledged individually above. No feedback was deferred. Shared-formula presence now also correctly marks uncached formula cells occupied.
- CI Verify passed before the review-fix pushes; final-head CI and permission to resolve the three addressed threads remain the readiness gates. No merge conflicts observed. The PR will remain unmerged.

## Open questions
- None. The user confirmed Monday–Sunday weeks and authorized the export-supported irregular-block mapping. Personal dates and source annotations stay private; repository examples remain synthetic.
