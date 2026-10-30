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
- [x] Address the integrity-review follow-up: explicit coach rep guidance suppressed by program_blank_rep_targets must not inherit native time targets; add a regression and retain provenance.
- [x] Update any affected canonical guidance, rerun focused and canonical offscreen checks, compilation/diff and dependency verification as needed, and review the incremental fixes with Brooks.
- [x] Fix Codex4429060440: block selected-week rep guidance that is blanked and cannot be retained by own-row notes; verify reviewed mode retains it.
- [x] Fix Codex4429060446: reconcile only missing-rep issues resolved by verified native duration binding without weakening other missing-target checks.
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
- Incremental integrity review found a follow-up to4428974724: the blank-rep policy hides explicit numeric reps from resolved values, so native-time binding must check retained source provenance before inheriting. This is actionable and included before the final review.
- Saved4428974736 in0a9898f and acknowledged it after push (reaction466630058). All three original findings have separate fix commits and thumbs-up reactions; no threads were manually resolved.
- Integrity follow-up: native time fallback now refuses authored base Reps, retained rep-field text after a blank-target policy, and unparsed selected-week instructions. RIR-only supported plan cues still retain native time. Independent source/output audits reject conflicting authored guidance. Added five regressions, including AMRAP and explicit base/weekly rep suppression.
- Validation: full local suite passed559 tests after the three Codex fixes, then562 tests after the first provenance guard. Final provenance changes passed56 focused tests (38 in the narrow binder/output subset); compilation/diff pass. The final whole-program suite passed303 tests after the AMRAP/RIR cases; hosted final-head CI repeats the complete suite.
- Private off-season replay after the fixes passed both audits, preserved both30-second targets, matched all759 non-note cells and left all input hashes unchanged. No dependency versions changed; final CI will repeat the locked audit.

## Brooks-Lint Review

**Mode:** PR Review

**Scope:** Incremental PR #29 fixes since63d11ff: native-time/source priority in template and output/source audits, selected-week note mapping context, reviewed-mode numeric durations, synthetic regressions and matching guidance. Sampled high-risk changed paths; no generated code excluded.

**Health Score:** 100/100

**Trend:** Stable at100.

The fixes preserve explicit source instructions and keep note content separate from mapping context, without adding dependencies or unrelated behavior.

### Findings

No remaining actionable R1–R6 or Quick Test Check findings. The added context reader stays inside the independent audit boundary and consumes only selected planned members of the verified pairs. The time-fallback predicate distinguishes defaults, authored targets and unresolved guidance; independent read-back checks enforce the same source priority. Regression assertions observe exported cells, source immutability and blocked unsafe cases rather than mock wiring.

### Summary

- Resolved all three Codex P2 concerns in separate commits and acknowledged each after its successful push.
- Resolved the integrity-review follow-up for blanked and unparsed rep instructions; unsupported prose remains blocked where notes are disabled.
- Save this final review/fix checkpoint, request final-head Codex review and wait for CI. Final hosted status belongs in the PR description, avoiding a status-only commit after review; leave the PR unmerged.
- Second Codex pass on85cc1a5 found4429060440 (weekly rep guidance lost under blank-rep + row-only policy) and4429060446 (stale missing-rep errors after native-time binding). Both are actionable. Final-head CI123 passed564 cases with one expected Linux platform skip, including audit/compile/diff. Add focused regressions and save/acknowledge each fix separately.
- Fix4429060440: row-only mode now blocks weekly numeric reps when neither structured targets nor equivalent own-row guidance retain them. Reviewed-note mode retains selected-week guidance; matching own-row numeric notes still work. Deferred Read-week instructions cannot fall back to different rep defaults while losing the weekly prescription. Added three regression cases, updated the existing weekly-blanking case to explicit reviewed mode, and passed58 focused tests.
- Saved4429060440 in5d8d6b3 and acknowledged it after push.
- Fix4429060446: after native duration binding, preview retires only exact missing-minimum/maximum-reps diagnostics for one matching source row/day/exercise/cycle whose native per-set time target resolved the omission. Missing RIR/rest/type, unrelated reps and ambiguous rows keep their blockers. Added four strict native-time regressions covering generation, source/output audits and input hashes; builder41 focused checks pass.
