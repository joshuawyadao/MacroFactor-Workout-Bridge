# Plan

Calibrate the bridge from the finalized Week 1 files without weakening its conservative matching. Add exact row-context disambiguation, pair superset sets in exercise order, and surface the exercise notes that MacroFactor actually includes in its workbook export.

## Scope
- In: exact companion-cell matching for duplicate coach labels, paired-set superset output, MacroFactor Active Program exercise-note reporting, private Week 1 mapping calibration, tests, and user documentation.
- Out: fuzzy matching, inferred skipped workouts, automatic insertion of arbitrary note text into coach result cells, reverse program import, and assumptions about session notes that are absent from the export.

## Action items
[x] Add an optional exact coach-row context alias to configuration and use it only to filter otherwise matching coach rows.
[x] Calibrate Hanging Straight Leg Raise to the main `Abs` row using its exact hanging-leg-raise variation, leaving the optional GHD row unmatched.
[x] Format supersets by aligned set position as `weight/weight x reps/reps`, grouping repeated weight pairs and separating weight-pair changes with semicolons.
[x] Read non-empty Active Program exercise notes from `.xlsx` exports and show relevant notes in preview/review reports without writing them into result cells.
[x] Add or update anonymized tests for row disambiguation, paired supersets, weight changes, mismatched set counts, and note reporting.
[x] Update the README and local workflow documentation with the matching, superset, and note-export behavior and limitations.
[x] Run targeted and complete tests, validate a private Week 1 preview against the finalized inputs, and confirm both personal source hashes remain unchanged.
[x] Commit and push only repository implementation files on `feat/local-file-workspace`; keep private mappings, exports, reports, and generated workbooks out of Git.

## Open questions
- None.
