# Plan

Calibrate the private Part 1 transfer mapping using existing exact aliases and per-exercise weight conversion. Add anonymized end-to-end regressions and document weight versus repetitions.

## Scope
- In: active private mapping, six confirmed per-side rules, exact substitutions, synthetic tests, transfer documentation.
- Out: Part 2 configuration, workbook edits, machine labels, base weight, generic inference, formatter redesign, app rebuild.

## Action items
[x] Inspect README, local-file workflow, configuration, formatter, matching and tests.
[x] Checkpoint the plan on the approved branch.
[ ] Back up and update the active private mapping while preserving existing aliases and excluding private data from Git.
[ ] Add synthetic preview/apply regressions for six per-side rules, unchanged reps, substitutions, zero load, total-load exercises and occupied-cell protection.
[ ] Document per-side weights and unchanged repetitions in README and local-file workflow.
[ ] Validate mappings against the labeled workbook without altering it; run targeted and broader tests and diff checks.
[ ] Commit and push tests and docs; report the separately saved private configuration.

## Open questions
- None. Branch and six weight conversions are confirmed; repetitions remain unchanged.
