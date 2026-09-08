# Plan

Add an opt-in empty-day review marker that writes `Skip` into the first available result cell of a programmed day with no matched MacroFactor session, highlights that cell yellow, and keeps the marker visible in preview and reports. Preserve conservative matching, occupied-cell protection, workbook structure, and explicit configuration so the behavior is reviewable rather than silent inference.

## Scope
- In: configurable marker text and fill, worksheet day-section discovery, missing-day preview proposals, OOXML highlight styles, desktop preview visibility, anonymized tests, README and local-workflow documentation, regenerated personal output, and branch save.
- Out: changing MacroFactor data, marking a day when unmatched or ambiguous export rows make absence uncertain, overwriting occupied cells, changing exercise matching or conversions, modifying source workbooks, and merging the feature branch.

## Action items
[x] Add validated workbook configuration for an optional empty-day marker and yellow fill.
[x] Discover repeated day sections without fixed worksheet names or row numbers and select the first eligible empty result cell per section.
[x] Propose markers only when the selected range contains usable workout data, the section has no matched results, and unmatched or ambiguous rows do not make the absence uncertain.
[x] Extend OOXML output to apply a yellow fill while preserving the target cell's font, border, alignment, number format, and unrelated workbook parts.
[x] Show review markers clearly in CLI, desktop preview, and machine-readable reports.
[x] Add anonymized tests for marker creation, highlighting, occupied cells, present days, uncertainty suppression, and source/workbook integrity.
[x] Update README and local workflow documentation to explain that yellow `Skip` values are review markers, not MacroFactor skip records.
[x] Regenerate and validate the current Week 2 output, run the focused and full suites plus workbook checks, rebuild the local macOS app, then commit and push the feature branch.

## Open questions
- None.
