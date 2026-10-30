# Plan

Fix the three actionable Codex findings on PR #29 while preserving native duration targets, own-row notes and explicit legacy policy behavior.

## Scope
- In: native-time precedence over rep defaults; selected-week mapping context in the note audit; reviewed-mode duration audit without note retention; synthetic regressions, validation and per-finding saves/reactions.
- Out: unrelated application behavior, personal workout data, dependency changes and merging the PR.

## Action items
- [x] Inspect the three non-outdated Codex review threads, source/template/audit paths and existing duration/row-note/batch tests; retain the verified-name/export contract described in Program-Generation and Configuration.
- [x] Fix comment 4428974724: distinguish default reps from explicit source replacements, preserve matching native times, test source/output audit agreement, then save/push and add thumbs up.
- [x] Fix comment 4428974729: use the selected planned-week mapping context in the independent note audit while sourcing note text only from the own row, then save/push and acknowledge.
- [x] Fix comment 4428974736: accept parsed durations in reviewed-mode audits when notes are disabled, verify a complete batch, then save/push and acknowledge.
- [ ] Update any affected canonical guidance, rerun focused and canonical offscreen checks, compilation/diff and dependency verification as needed, and review the incremental fixes with Brooks.
- [ ] Request Codex review on the final head, wait for passing CI Verify and terminal review, refresh mergeability and report the unmerged PR's readiness.

## Open questions
- None. The requested full review cycle authorizes all three narrow fixes.

## Review ledger
- PR #29: base 62db9dc; previous head 63d11ff. Brooks/integrity reviews were clean, 79 focused tests passed, and CI Verify run41137021790 passed548 cases with one expected Linux platform skip.
- Codex completed on63d11ff with three P2 findings (4428974724,4428974729,4428974736). All are actionable and will be saved/acknowledged separately. Threads remain unresolved as required by the review workflow.
- Fix4428974724: native duration binding distinguishes config_default reps from explicit source/reviewed targets, blanks only defaults when retaining native times, and blocks ambiguous timed identity. The full base audit agrees; new duration-default integration tests cover preview, generation, both audits and unchanged hashes. Focused68 tests pass; compilation/diff clean.
- Saved4428974724 in965a0cc and added thumbs up after push. Parent51 focused checks and builder68 focused checks passed.
- Fix4428974729: independent note audit reads only selected planned-week cells for exact mapping context, honors pair direction and inherited headers, and keeps exported note text restricted to base cells. Six new regressions cover valid selected/inherited context, reversed pair direction, excluded completed results, unselected weeks and base-mode separation;53 focused checks pass.
- Saved4428974729 in34f9372 and added thumbs up after push.
- Fix4428974736: the reviewed-note legacy audit exempts independently parsed duration targets from the unsupported-reps guard. A full generated batch now retains30-second native targets with no Notes; unsupported prose remains blocked. Two batch regressions and the related focused audit suite pass.
