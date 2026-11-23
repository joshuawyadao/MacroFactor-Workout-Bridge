# Plan

Format confirmed partial reps as `+Np` in coach-workbook results and integrate the rep review editor with the current transfer logic.

## Scope

- In: Part 1 rep confirmations, compact workbook notation, desktop and CLI previews, dated correction compatibility, tests and documentation.
- Out: Source workbooks, numeric history, installed app bundles, and private workout data.

## Action items

- [x] Compare the reviewed tracker with prior export values and review transfer documentation, tests, and the existing rep-confirmation branch.
- [x] Checkpoint this plan on `codex/separate-full-partial-reps` and integrate the current `origin/main`.
- [x] Render confirmed full and partial counts as `8+3p` for regular sets, myo sets, drop sets, and eligible supersets. Keep source reps numeric and support explicit splits on exported integers.
- [x] Compose rep review with dated result corrections, current load grouping, and stale-input protection. Preserve raw decimal transfer when rep review is disabled.
- [x] Update the formatter, transfer, and desktop regressions. Cover an integer and a fractional export, unchanged myo mini-set notation, and precedence for a valid dated correction.
- [x] Update Architecture, Configuration, CLI Reference, and Desktop Guide. Verify the selected-date review and private confirmation storage described in Local File Workflow.
- [x] Run focused transfer and desktop tests, the full offscreen suite, compilation, and diff checks.
- [x] Stage the resolved integration and save it on the existing branch. Publication and hosted verification are tracked in [PR #28](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/pull/28).

## Open questions

- None.

## Validation

- Plan checkpoint `9706320`. Integrated main at `f69d85b`.
- Passed 92 focused tests, all 634 tests in the canonical offscreen suite, Python compilation, and Git whitespace checks.
- Independent review checked confirmation precedence, stale inputs, and shared workbook targets. Synthetic test data covered both integer and fractional exports.

## Prior work

- [Rep-confirmation design, reviews, and validation](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/blob/9f97f3c1bce953ab62d6e7d55a100657b11961d3/docs/Implementation-Plan.md)
- [Main CI verification record](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/blob/f69d85bbae3c7ddf96d690c20d8191937b1cb09c/docs/Implementation-Plan.md)
