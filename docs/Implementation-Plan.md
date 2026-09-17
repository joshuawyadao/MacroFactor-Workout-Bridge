# Plan

Clarify navigation by making Dashboard the first/default main tab and naming the workbook-transfer tool by its purpose. Align secondary view names, feedback labels and workbook action copy without changing analysis or write behavior.

## Scope
- In: main tab order/names, concise workflow explanation, secondary labels/tooltips, related GUI tests/docs, version 0.9.1 build, commit and push.
- Out: app/bundle renaming, data/schema/calculation changes, changing workbook safety, moving tools into a new menu, automatic installation, PR/merge.

## Action items
[x] Inspect navigation, workflow copy, existing GUI assertions, README and Local-File-Workflow.
[x] Make Dashboard the first/default main tab and Update coach workbook the second; retain stable widget references for tests/navigation.
[x] Align Overview, Exercise trends, Block summaries, Compare blocks and Training notes labels, feedback-save wording, and workbook load/save actions.
[x] Update related docs and tests, including startup order, hidden-view navigation, keyboard access and both workflows at 900×680.
[x] Run targeted and full tests, inspect screenshots, package 0.9.1/build 13, and verify smoke launch/signature without modifying private data.
[x] Commit and push scoped changes with save-branch.

## Open questions
- None. Keep Weekly feedback visible and preserve all functionality. This is a navigation/copy update; the installed app remains unchanged until replacement is requested.

## Verification notes
- `scripts/test.sh`: all 177 tests passed. `git diff --check`, packaged 0.9.1/build 13 smoke launch, and deep/strict signature verification passed. No installed bundle or private-data migration was performed.
- Updated desktop, explorer and comparison GUI tests; three targeted navigation/workbook tests passed. Keyboard navigation reaches both main tabs, secondary notes remain accessible, and workbook save still creates only a separate copy with unchanged source hashes.
- Visual QA of both main tabs at 1120×820 and 900×680 and the renamed Training notes form passed. Real-data preview still shows 2,461 sets from seven exports; read-only QA left saved feedback unchanged.
- README and Local-File-Workflow now use the actual tab/action labels and explain that workbook updating is optional and separate from dashboard analysis and feedback.
