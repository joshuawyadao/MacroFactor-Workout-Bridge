# Plan

Address the three confirmed Brooks review findings for PR #19 without expanding the dashboard feature scope. Preserve exact workout recency, make original-set inspection robust to invalid weight values, and retain private-note conflict protection when a workspace switch fails.

## Scope
- In: default variation ordering, nonfinite weight presentation in set details, failed workspace-switch save protection, regression tests, relevant README/Local-File-Workflow documentation, validation, commit and push.
- Out: changing import/matching or analysis rules, data migrations, recovery predictions, coach-program export integration, installed-app replacement, PR merge or review-thread resolution.

## Action items
[x] Review the branch diff and high-risk ingestion, analytic, GUI and test paths; read README and docs/Local-File-Workflow.md.
[x] Rank default variations by actual latest workout date, with deterministic same-date ties and compatibility for summary-only dashboards; cover same-week recency.
[x] Display accepted nonfinite source weights explicitly in set details without quantizing or changing calculations; cover Infinity, -Infinity and sNaN through the normal import/dashboard path.
[x] Preserve the displayed feedback file's path/hash guard after a failed workspace switch, including a preceding manual file override; test external edits and successful replacement.
[x] Update README/Local-File-Workflow with clarified recency, invalid-weight display, and retained-data protection.
[x] Run focused regressions, the full test suite, compilation and diff checks; review the patch and privacy scope.
[x] Prepare validated fixes for save-branch; continue Codex/CI review on the resulting PR head without merging.

## Open questions
- None. The fixes preserve existing documented behavior and local source immutability. App installation is separate from this PR workflow.

## Review ledger
- Initial head c73d7b8: 177 tests passed; installed 0.9.1/build 13 launch and source/feedback-preservation checks passed.
- Brooks P2: default selection used week starts rather than actual workout dates, so alphabetic ordering could select an older same-week variation.
- Brooks P2: source-set detail formatting quantized accepted nonfinite weights and raised InvalidOperation, despite aggregate metrics excluding them safely.
- Brooks P2: choosing a new workspace cleared the loaded snapshot before success; a failed load left the old save form active without its external-change guard.
- PR #19 opened against main; Codex requested; CI Verify running. No CI failure or merge conflict observed yet.
- Focused validation: 19 analytical tests, 10 timeline GUI tests, and 24 managed-history/GUI tests pass. The numeric and recency regressions reproduced failures before their fixes. Compilation and diff checks pass; complete suite running.
- Initial Codex review of c73d7b8 completed with no major issues or inline threads; a refreshed review will be requested after these fixes are pushed.
- Follow-up patch review found that a preceding manual override could leave the retained managed snapshot pointing to a different feedback file. Track the displayed file's guard independently and update it on every successful manual/managed load before saving; do not change source selection or broaden manual-mode behavior.
- Follow-up reproduction confirms both manual-override cases now pass: edits to unrelated prior-workspace feedback do not block the displayed form, while external edits to the displayed feedback file are refused without losing the form text. No remaining actionable Brooks finding in the sampled patch.
- Initial CI Verify passed on c73d7b8, including dependency audit, complete tests, compilation and diff checks; no CI failure or conflict fix was required.
- Final local validation: `scripts/test.sh` passed all 183 tests in 395.044s; 26 focused managed-history/GUI tests passed after the manual-override extension. Compilation, diff checks and the source app-entry smoke test passed. Six regression tests were added across three test modules. No private files or installed bundle were modified.
- Final-head GitHub checks and Codex review are tracked on PR #19 after save-branch pushes this patch; local verification alone is not a merge-readiness claim.
