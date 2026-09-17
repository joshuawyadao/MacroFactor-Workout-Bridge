# Plan

Address the three confirmed Brooks review findings for PR #19 without expanding the dashboard feature scope. Preserve exact workout recency, make original-set inspection robust to invalid weight values, and retain private-note conflict protection when a workspace switch fails.

The subsequent Codex review adds three narrow follow-ups: apply the same conflict guard in manual mode, open the latest logged mapped coach week for feedback, and normalize nonfinite values for stable snapshot reconciliation. Address and save each comment independently before the final broad validation.

## Scope
- In: default variation ordering, nonfinite weight presentation and snapshot comparison, displayed-note protection in automatic and manual modes, latest mapped feedback-week navigation, regression tests, relevant documentation, validation, commit and push.
- Out: changing import/matching or analysis rules, data migrations, recovery predictions, coach-program export integration, installed-app replacement, PR merge or review-thread resolution.

## Action items
[x] Review the branch diff and high-risk ingestion, analytic, GUI and test paths; read README and docs/Local-File-Workflow.md.
[x] Rank default variations by actual latest workout date, with deterministic same-date ties and compatibility for summary-only dashboards; cover same-week recency.
[x] Display accepted nonfinite source weights explicitly in set details without quantizing or changing calculations; cover Infinity, -Infinity and sNaN through the normal import/dashboard path.
[x] Preserve the displayed feedback file's path/hash guard after a failed workspace switch, including a preceding manual file override; test external edits and successful replacement.
[x] Update README/Local-File-Workflow with clarified recency, invalid-weight display, and retained-data protection.
[x] Run focused regressions, the full test suite, compilation and diff checks; review the patch and privacy scope.
[x] Prepare validated fixes for save-branch; continue Codex/CI review on the resulting PR head without merging.
[x] Protect manual-mode annotation saves from external updates (Codex comment 4040032862); add regression coverage and documentation. Four focused GUI tests pass; save/push and acknowledgement follow this checkpoint.
[x] Navigate Weekly feedback backward through logged weeks to the latest selectable mapped week (Codex comment 4040032847); preserve unsaved text, add boundary tests and documentation. Four focused GUI checks pass; save/push and acknowledgement follow this checkpoint.
[x] Normalize nonfinite decimal signature values without altering original records (Codex comment 4040032852); three ingestion regressions and all 13 managed-history tests pass. Save/push and acknowledgement follow this checkpoint.
[ ] Increase CI Verify's job budget from 10 to 15 minutes after the observed timeout; retain every test, audit and validation step, then verify a terminal green run.
[ ] Run the complete suite, compilation and smoke checks; finish final-head CI/Codex review and mergeability checks. Resolve fixed threads only with explicit user approval; do not merge.

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
- d04d880 pushed with all three Brooks fixes. Codex's review of that head produced the three follow-ups above; all are accepted as in-scope. No human product choice is needed. An asynchronous question requests permission to resolve the fixed review threads after validation.
- CI run 35256496103 reached `Ran 183 tests in 575.285s` and `OK`, but the job hit its 10-minute timeout before compile/diff checks. This is a bounded workflow-timeout fix caused by the expanded regression suite, not a test failure; no test assertion is weakened or removed.
- Codex 4040032862: removed the automatic-mode bypass from the displayed-file save guard. The manual external-edit regression failed before the fix and passed after it, together with automatic conflict protection, failed-switch/manual behavior and a successful manual save (four targeted GUI tests).
- Codex 4040032852: stable hashable nonfinite signature tokens preserve type/sign/payload while keeping original records unchanged. Three real ingestion regressions cover equivalent exports, genuine repeated-set supersets and different-value conflicts; all 13 managed-history tests pass. Manual-save fix was pushed as fc16e2b and acknowledged with a thumbs-up.
- Codex 4040032847: search logged weeks backward for the latest mapped selectable block; when none is mapped, keep the view and selection unchanged. Two boundary regressions plus secondary navigation and unsaved-feedback preservation pass (four focused GUI tests). The synthetic fixture names Archive's first week Week 9, which the assertion now matches. Independent follow-up review found no implementation issue in the three Codex fixes. Nonfinite reconciliation was pushed as 360e333 and acknowledged with a thumbs-up.
