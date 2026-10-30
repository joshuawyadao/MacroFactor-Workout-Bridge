# Plan

Fix the three actionable Codex findings on PR #29 while preserving native duration targets, own-row notes and explicit legacy policy behavior.

## Scope
- In: native-time precedence over rep defaults; selected-week mapping context in the note audit; reviewed-mode duration audit without note retention; synthetic regressions, validation and per-finding saves/reactions.
- Out: unrelated application behavior, personal workout data, dependency changes and merging the PR.

## Action items
- [x] Inspect the three non-outdated Codex review threads, source/template/audit paths and existing duration/row-note/batch tests; retain the verified-name/export contract described in Program-Generation and Configuration.
- [x] Fix comment 4428974724: distinguish default reps from explicit source replacements, preserve matching native times, test source/output audit agreement, then save/push and add thumbs up.
- [ ] Fix comment 4428974729: use the selected planned-week mapping context in the independent note audit while sourcing note text only from the own row, then save/push and acknowledge.
- [ ] Fix comment 4428974736: accept parsed durations in reviewed-mode audits when notes are disabled, verify a complete batch, then save/push and acknowledge.
- [ ] Update any affected canonical guidance, rerun focused and canonical offscreen checks, compilation/diff and dependency verification as needed, and review the incremental fixes with Brooks.
- [ ] Request Codex review on the final head, wait for passing CI Verify and terminal review, refresh mergeability and report the unmerged PR's readiness.

## Open questions
- None. The requested full review cycle authorizes all three narrow fixes.

## Review ledger
- PR #29: base 62db9dc; previous head 63d11ff. Brooks/integrity reviews were clean, 79 focused tests passed, and CI Verify run41137021790 passed548 cases with one expected Linux platform skip.
- Codex completed on63d11ff with three P2 findings (4428974724,4428974729,4428974736). All are actionable and will be saved/acknowledged separately. Threads remain unresolved as required by the review workflow.
- Fix4428974724: native duration binding distinguishes config_default reps from explicit source/reviewed targets, blanks only defaults when retaining native times, and blocks ambiguous timed identity. The full base audit agrees; new duration-default integration tests cover preview, generation, both audits and unchanged hashes. Focused68 tests pass; compilation/diff clean.
