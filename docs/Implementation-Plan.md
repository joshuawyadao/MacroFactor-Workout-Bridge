# Plan

Make program generation verify MacroFactor exercise names against native exports, preserve duration targets, and export notes exclusively from each exercise's own left-table row by default.

## Scope
- In: offline program preview/generate/batch pipeline, private native name references and integrity checks, optional Set N Duration columns, row-scoped notes, independent audits, synthetic regressions and documentation.
- Out: hosted APIs, inferred exercise catalogs, fuzzy substitutions, desktop generation UI, coach workbook edits, personal data commits, pull requests and merging.

## Action items
- [x] Inspect Program-Generation, Program-Batch, Configuration, Architecture and Development guidance and affected parser/template/audit tests; use the user-selected branch codex/program-export-contracts.
- [ ] Verify exact exercise names against the selected native program export and optional private native references; block missing evidence and protect reference hashes during generation.
- [ ] Model movement duration separately from reps/rest; read, write and audit optional Set N Duration columns, preserving associated native targets and clearing stale or inactive values.
- [ ] Default notes to each exercise's own left-table row; exclude weekly and neighboring content and unscoped configured notes, with explicit opt-in for reviewed legacy overrides.
- [ ] Add synthetic regressions for unknown names and reference drift, duration preservation and resizing, and shared names with different row notes.
- [ ] Update Program-Generation, Program-Batch, Configuration, Architecture and anonymous config examples.
- [ ] Run focused tests, the canonical offscreen suite, compilation and diff checks, then replay the successful private workflow without committing personal data.
- [ ] Create coherent local checkpoints and push the completed branch with the save-branch workflow.

## Open questions
- None. The user selected the branch. Name evidence comes from private native exports rather than a bundled inferred catalog; row-only notes are the default.
