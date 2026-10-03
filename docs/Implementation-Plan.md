# Plan

Make completed-set formatting omit a repeated weight when regular sets lead into a myo set at the same load. Preserve mini-set notation, explicit weight changes and workbook-transfer safeguards, and verify that corrected reps continue to come directly from a fresh source export.

## Scope
- In: formatting.py, synthetic formatter and workbook-transfer regressions, result-formatting guidance in docs/CLI-Reference.md, local checkpoints and a pushed feature branch.
- Out: private exports/workbooks/mappings, automatic rep corrections, inferred exercise replacements, warm-up copying, program-generation behavior, dependency changes, app installation and pull request creation.

## Action items
[x] Trace the shared formatter, export importer and transfer path; read docs/Development.md, docs/CLI-Reference.md and existing formatting/integration coverage.
[ ] Create codex/compact-myo-results from this worktree's current commit and checkpoint the resolved plan.
[ ] Add synthetic regressions for regular-to-myo same-load grouping, per-side conversion, changed loads and boundaries after drop/myo series; cover preview and saved workbook output.
[ ] Update the myo activation formatter to reuse the preceding regular-set weight group only when its load is unchanged.
[ ] Document the compact format and fresh-export requirement for corrected source reps in docs/CLI-Reference.md.
[ ] Run focused tests, the canonical offscreen suite, compilation, dependency audit and diff checks; record results and inspect the final diff.
[ ] Commit the completed change and plan, then push the feature branch with task files only.

## Open questions
- None. Corrected rep counts are source data and must never be guessed or hard-coded. Existing behavior for a regular set after a myo series remains unchanged.
