# Plan

Accept MacroFactor's current singular-pound exercise-log header without weakening the bridge's exact import contract, then use the corrected importer to archive and process the September 8 inputs into a safe, verifiable Week 2 coach-workbook copy.

## Scope
- In: exact support for both `Weight (lb)` and `Weight (lbs)`, anonymized CSV/XLSX regression coverage, user-facing import documentation, local intake/archival, Week 2 preview and output generation, and workbook/source-integrity validation.
- Out: importing results from the coach workbook, inferring a missing workout or an optional-day skip, automatically copying warm-ups or equipment notes, changing unrelated exercise conversions, modifying either original personal file, and merging the feature branch.

## Action items
[x] Add a small canonical-header layer so current and legacy MacroFactor pound headers produce the same internal records.
[x] Add anonymized tests proving singular-header CSV and XLSX exports import successfully while legacy plural headers continue to work.
[x] Document the accepted exact pound-header variants and the missing-workout safety behavior.
[x] Re-archive the new inputs, update the private exact exercise mapping from coach-confirmed evidence, and preview Week 2 against an empty-result workbook.
[x] Generate a separate partial Week 2 workbook containing only sessions present in the MacroFactor export.
[x] Compare the generated values with the user's updated coach workbook and validate workbook structure, formulas, styles, source hashes, and review reports.
[x] Run the complete relevant test suite and checks, mark this plan complete, commit, and push the feature branch for review.

## Open questions
- None.
