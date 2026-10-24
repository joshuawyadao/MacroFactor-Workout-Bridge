# Plan

Display confirmed full and partial rep counts separately in coach-workbook imports while preserving MacroFactor's original numeric reps for history and source verification.

## Scope
- In: explicit per-set full/partial counts, coach-result formatting, transfer preview and CLI input, private confirmation persistence, regression tests, and affected user documentation.
- Out: guessing counts from decimal reps, changing source exports or existing generated workbooks, changing history calculations, automatic equipment conversions, and installing or replacing the packaged app.

## Action items
- [x] Inspect Architecture.md, CLI-Reference.md, Local-File-Workflow.md, Desktop-Guide.md, Development.md, importer/model/formatter paths, and existing integration, numeric, and desktop tests.
- [x] Verify the supplied export's schema and official MacroFactor full/partial logging and data-export documentation. The supplied Workout Log has only a combined Reps column; separate counts cannot be uniquely recovered.
- [x] Resolve the confirmation workflow and detached-branch questions below, then checkpoint this plan on the selected branch. The user approved the preview editor and codex/separate-full-partial-reps branch, including commit and push.
- [x] Add a narrowly scoped full/partial confirmation contract keyed to the export hash and original set identity, retaining raw Reps for history and refusing stale or invalid confirmations.
- [x] Integrate confirmed counts with coach-result formatting, including repeated loads, converted weights, special sets, and paired supersets. Preserve legacy integer-only formatting and make unresolved fractional sets visible for review.
- [x] Expose set confirmation in the desktop transfer preview and a corresponding explicit CLI input, saving confirmation data only in private workspace storage without modifying exports.
- [x] Add synthetic regression tests for import/preview/apply, full-only and partial-only counts, ambiguous decimals, malformed or stale confirmations, unchanged numeric history, special-set formatting, and desktop review behavior.
- [x] Update CLI-Reference.md, Desktop-Guide.md, Local-File-Workflow.md, Configuration.md, and Architecture.md to describe the supported data, confirmation step, display, and preservation boundaries.
- [x] Run targeted formatter/integration/numeric/desktop tests, the complete offscreen suite via scripts/test.sh, compilation, and git diff --check; review the final diff and privacy boundaries.
- [x] Record validation and checkpoint commits and prepare the completed branch for the final save-branch commit and push; the final chat report records publication.

## Open questions
- None. Use an explicit per-set preview editor and remember confirmations for the same export. Create and save codex/separate-full-partial-reps. Preserve original numeric history and exports.

## Validation and save record

- Plan checkpoint: b259656. Core, CLI and transfer regression checkpoint: f1c39e8.
- Final canonical `./scripts/test.sh`: 523 tests passed, zero skips, exit 0. Focused core/transfer/numeric/safety suite: 57 tests passed. Focused Qt editor/desktop/model suite: 19 tests passed.
- Source compilation and `git diff --check` passed. Synthetic offscreen preview/editor rendering verified the new controls and displayed state. Private workout files were not used as automated fixtures or included in commits.
- Independent workbook-integrity review found one editor validation issue: invalid Save closed the dialog and discarded edits. Validation now runs inside the editor; real button-click coverage verifies values survive invalid Save. Re-review found no remaining actionable issues.
- Confirmations remain private and tied to export bytes and original set identity; raw history calculations, exports and existing workbooks are unchanged. Save checks preserve unrelated-date confirmations and detect observed external changes, without promising filesystem-wide locking.
- The installed app bundle is intentionally unchanged. Rebuild it from the completed branch to use the feature in a packaged application; source execution already includes the editor. No dependency or packaging changes were required.
