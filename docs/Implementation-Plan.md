# Plan

Match reviewed weekly results by compacting unchanged weights, retaining explicit per-side mappings, and applying dated result corrections only when their logged source sets still match.

## Scope
- In: completed-set formatting, optional dated/source-checked Part 1 result corrections with visible audit details, private confirmed mappings and corrections, synthetic regression coverage, documentation, and a reviewed PR into main.
- Out: inferred equipment conversions or partial reps, changing original exports or occupied coach cells, changing history statistics or future program prescriptions, publishing private workout data, and merging the PR.

## Action items
- [x] Compare the reviewed workbook with the generated copy; classify formatting, per-side conventions, and four dated logging corrections; confirm that dated corrections should be retained.
- [ ] Commit this resolved plan as the first checkpoint on `codex/week2-transfer-corrections`.
- [ ] Compact adjacent standard/myo sets at unchanged displayed weight while preserving mini-set notation, weight changes, drop boundaries, and superset pairing.
- [ ] Add validated `result_corrections` configuration scoped to date, workout, exact source exercise, and expected ordered logged sets; include it in preview/apply mapping fingerprints and expose applied/mismatched corrections in review output.
- [ ] Save the three confirmed per-side mappings and four corrections in ignored private configuration; verify the resulting preview against the reviewed cells without putting personal data into Git.
- [ ] Add synthetic formatter and preview/apply regressions covering correction guards, stale inputs/mappings, partial-rep text, nonmatching dates, occupied cells, and configured per-side loads.
- [ ] Update Configuration, Architecture, and CLI reference docs; run focused tests, the canonical offscreen suite, dependency audit, compilation, and diff checks.
- [ ] Run Brooks review, commit/push, open the PR into main, request Codex review, address actionable feedback, and follow required CI and mergeability to completion or a concrete blocker.

## Open questions
- None. The user confirmed retaining corrections for the specific workouts; unrelated dates and source records must remain unchanged.

## Validation and review ledger
- Workbook comparison found nine edited result cells: two formatting corrections, three per-side display corrections, and four logged-data corrections. Private values remain outside the repository.
- Latest `origin/main` matches the starting commit. The worktree had no unrelated tracked or staged changes.
