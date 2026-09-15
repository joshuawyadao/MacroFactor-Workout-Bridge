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
[ ] Verify the real irregular block with its confirmed three-week range; preserve sources and existing context with before/after backups.
[ ] Run the complete suite, compilation, diff checks, and rebuilt app smoke verification.
[ ] Commit and push the feature branch; shepherd the PR through reviews and CI without merging.

## Open questions
- None. The user confirmed Monday–Sunday weeks and authorized the export-supported irregular-block mapping. Personal dates and source annotations stay private; repository examples remain synthetic.
