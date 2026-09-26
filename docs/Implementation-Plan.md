# Plan

Calibrate the private Part 1 transfer mapping using existing exact aliases and per-exercise weight conversion. Add anonymized end-to-end regressions and document weight versus repetitions.

## Scope
- In: active private mapping, six confirmed per-side rules, exact substitutions, synthetic tests, transfer documentation.
- Out: Part 2 configuration, workbook edits, machine labels, base weight, generic inference, formatter redesign, app rebuild.

## Action items
[x] Inspect README, local-file workflow, configuration, formatter, matching and tests.
[x] Checkpoint the plan on the approved branch.
[x] Back up and update the active private mapping while preserving existing aliases and excluding private data from Git.
[x] Add synthetic preview/apply regressions for six per-side rules, unchanged reps, substitutions, zero load, total-load exercises and occupied-cell protection.
[x] Document per-side weights and unchanged repetitions in README and local-file workflow.
[x] Validate mappings against the labeled workbook without altering it; run targeted and broader tests and diff checks.
[x] Prepare final branch save; private configuration is backed up and installed separately.

## Open questions
- None. Branch and six weight conversions are confirmed; repetitions remain unchanged.

## Validation
- All 18 reviewed exercises match unique intended workbook rows; six half-weight/suffix rules and twelve unchanged-load rules verified.
- Targeted transfer/formatting/calibration/integration suite: 28 tests passed.
- Canonical suite (`./scripts/test.sh`): 445 tests passed, no skips.
- Compilation and `git diff --check`: passed.
- Private configuration was backed up before installation. No workbook edits, Part 2 configuration edits or app rebuild were needed.
