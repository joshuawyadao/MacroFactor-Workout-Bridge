# Plan

Match reviewed weekly results by compacting unchanged weights, retaining explicit per-side mappings, and applying dated result corrections only when their logged source sets still match.

## Scope
- In: completed-set formatting, optional dated/source-checked Part 1 result corrections with visible audit details, private confirmed mappings and corrections, synthetic regression coverage, documentation, and a reviewed PR into main.
- Out: inferred equipment conversions or partial reps, changing original exports or occupied coach cells, changing history statistics or future program prescriptions, publishing private workout data, and merging the PR.

## Action items
- [x] Compare the reviewed workbook with the generated copy; classify formatting, per-side conventions, and four dated logging corrections; confirm that dated corrections should be retained.
- [x] Commit this resolved plan as the first checkpoint on `codex/week2-transfer-corrections`.
- [x] Compact adjacent standard/myo sets at unchanged displayed weight while preserving mini-set notation, weight changes, drop boundaries, and superset pairing.
- [x] Add validated `result_corrections` configuration scoped to date, workout, exact source exercise, and expected ordered logged sets; include it in preview/apply mapping fingerprints and expose applied/mismatched corrections in review output.
- [x] Save the three confirmed per-side mappings and four corrections in ignored private configuration; verify the resulting preview against the reviewed cells without putting personal data into Git.
- [x] Add synthetic formatter and preview/apply regressions covering correction guards, stale inputs/mappings, partial-rep text, nonmatching dates, occupied cells, and configured per-side loads.
- [x] Update Configuration, Architecture, and CLI reference docs; run focused tests, the canonical offscreen suite, dependency audit, compilation, and diff checks.
- [ ] Run Brooks review, commit/push, open the PR into main, request Codex review, address actionable feedback, and follow required CI and mergeability to completion or a concrete blocker.

## Open questions
- None. The user confirmed retaining corrections for the specific workouts; unrelated dates and source records must remain unchanged.

## Validation and review ledger
- Workbook comparison found nine edited result cells: two formatting corrections, three per-side display corrections, and four logged-data corrections. Private values remain outside the repository.
- Latest `origin/main` matches the starting commit. The worktree had no unrelated tracked or staged changes.
- Plan checkpoint: `7bdfcb2`. Focused formatter, correction, desktop-model, numeric, preview/apply, and per-side tests pass. Private calibration reproduces all nine reviewed cells without changing any source file.
- Read-only correctness review identified two guard gaps: skipped XLSX rows could escape expected-set comparison, and unmatched workout names were silent. Corrections now withhold uncertain source rows and expose unused in-range policies. Synthetic XLSX and scope-visibility regressions pass.
- The private calibration retains existing review items for a shared sequential preacher row and an extra exercise with no coach row. Those require manual review and are not made into guessed mappings.
- Main's active ruleset requires `CI Verify`, linear history, resolved review threads, and squash merge; approval count is zero. The PR will remain unmerged.
- All 82 focused transfer/correction/formatter/model tests pass, Python compilation and diff checks pass, and all three dependency locks audit with no known vulnerabilities. The final canonical offscreen run passed 598 tests with exit status 0. Local source tests used Python 3.11.2; hosted CI selects the reviewed patched interpreter.
- PR #31 opened with application head `e73c29d`; its required `CI Verify` passed. Codex review found one P2 issue: signaling nonfinite values in raw correction sets could raise during Decimal equality. The comparison now checks finiteness first; a synthetic regression covers signaling/quiet NaN and Infinity in both weight and reps while retaining the unrelated preview.

## Brooks-Lint Review

**Mode:** PR Review

**Scope:** Branch changes vs `origin/main`; production policy, preview/apply safety, formatter boundaries, synthetic tests and documentation. The diff exceeds 500 lines; review focused on the complete production changes and the highest-risk synthetic cases.

**Health Score:** 100/100

**Trend:** Stable at 100 compared with the previous stored PR Review; this review does not write trend history.

The change keeps reviewed corrections explicit and scoped, with ordinary transfer safeguards and visible failure outcomes.

### Findings

No remaining actionable R1–R6 or Quick Test Check findings. Two review concerns were fixed before publication:
- Symptom: a skipped missing-date XLSX row could evade the complete-set expectation. Source: *Code Complete* — Defensive Programming. Consequence: a correction could be proposed from an incomplete source sequence. Remedy: withhold for uncertain matching/unidentified source rows and cover the case with a synthetic XLSX regression.
- Symptom: a renamed workout could leave an in-range correction unused without a review detail. Source: *A Philosophy of Software Design* — Information Leakage. Consequence: the user could miss that a reviewed correction was not applied. Remedy: report `not_applied` with scope and reason, preserve distinct-workout isolation, and suppress inferred day markers until reviewed.

### Summary
- Preserve exact mappings and final-text correction boundaries; do not infer equipment conversions or partial reps.
- Formatter and correction tests exercise changed behavior, source drift, occupied/shared targets and error paths without private fixtures or mock-heavy production seams.
- Hosted Codex review, required CI and mergeability still need terminal verification.
