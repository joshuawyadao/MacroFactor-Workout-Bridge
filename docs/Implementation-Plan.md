# Plan

Make program generation verify MacroFactor exercise names against native exports, preserve duration targets, and export notes exclusively from each exercise's own left-table row by default.

## Scope
- In: offline program preview/generate/batch pipeline, private native name references and integrity checks, optional Set N Duration columns, row-scoped notes, independent audits, synthetic regressions and documentation.
- Out: hosted APIs, inferred exercise catalogs, fuzzy substitutions, desktop generation UI, coach workbook edits, personal data commits, pull requests and merging.

## Action items
- [x] Inspect Program-Generation, Program-Batch, Configuration, Architecture and Development guidance and affected parser/template/audit tests; use the user-selected branch codex/program-export-contracts.
- [x] Verify exact exercise names against the selected native program export and optional private native references; block missing evidence and protect reference hashes during generation.
- [x] Model movement duration separately from reps/rest; read, write and audit optional Set N Duration columns, preserving associated native targets and clearing stale or inactive values.
- [x] Default notes to each exercise's own left-table row; exclude weekly and neighboring content and unscoped configured notes, with explicit opt-in for reviewed legacy overrides.
- [x] Add synthetic regressions for unknown names and reference drift, duration preservation and resizing, and shared names with different row notes.
- [x] Update Program-Generation, Program-Batch, Configuration, Architecture and anonymous config examples.
- [x] Run focused tests, the canonical offscreen suite, compilation and diff checks, then replay the successful private workflow without committing personal data.
- [x] Create coherent local checkpoints and push the completed branch with the save-branch workflow.

## Open questions
- None. The user selected the branch. Name evidence comes from private native exports rather than a bundled inferred catalog; row-only notes are the default.

## Validation record
- Implementation checkpoint: 287 focused program tests pass. New identity, duration and same-row note regressions use only synthetic workbooks. Existing legacy-note tests explicitly select reviewed mode and supply native-name fixtures.
- Final private replay passes full source and independent output audits for all 24 exercises (730 audited cells). All 759 non-note cells match the successful native export, both timed plank targets remain numeric 30-second values parsed from the source, and only worksheet/shared-string package parts differ. Every input hash is unchanged; private inputs and generated reports remain ignored.
- The completed full offscreen run passed 548 tests in 67.636 seconds, exit 0, with no skips. The initial full run hit a background-load drift guard in an unrelated managed-GUI setup; that test passed in isolation and on the full rerun. The subsequent preview display change passed all 40 related CLI/preview/generation tests; final compilation and diff checks pass.
- Compilation and diff checks pass; no dependencies changed. The existing pinned dependency locks report no known vulnerabilities.
- Read-only workbook integrity review found and resolved compact-duration parsing, guarded time-override provenance and ambiguous native-time loss. Ambiguous time identity now blocks rather than erasing a target.
- Preview follow-up: CLI output shows common/per-set time targets and marks timed reps as not applicable, so the reviewed numeric duration is visible before generation.
- Saved `codex/program-export-contracts` to origin with plan checkpoint `2cd061f`, implementation checkpoint `63e84f5` and preview follow-up `04f1177`. This final documentation-only completion record follows the successful push. No private workbooks, reports or local profiles are staged.

## Brooks-Lint Review

**Mode:** PR Review

**Scope:** PR #29 versus main `62db9dc`; sampled the highest-risk changed program parser, configuration/models, name verifier, service, template writer, source/output audits, batch publication, CLI and corresponding synthetic tests. No generated files were excluded. The review is scoped to this program-export change.

**Health Score:** 100/100

**Trend:** Stable at 100.

The change enforces one coherent export contract without new runtime dependencies or unrelated application behavior.

### Findings

No actionable findings across R1–R6 or the Quick Test Check. Native identity verification, duration binding and own-row note formatting have small external interfaces; immutable prescription fields retain source provenance. Independent source/output grammars deliberately remain separate from the production parser/writer, while shared note formatting accepts only one literal row. Tests cover successful exports, ambiguous identities, malformed evidence, drift, stale cells, source-row isolation and tampered outputs. Temporary synthetic workbooks and bounded mutation seams keep failures observable without external personal data.

### Summary

- The diff exceeds 500 lines across 35 related files, a change-propagation review signal. The changed files remain inside one export contract and its fixtures/docs; no unrelated fan-out was found.
- Native durations fail closed when their identity cannot be proven. A conservative block for the same timed name appearing under changed workout identity is an intentional safety tradeoff rather than silently clearing a target.
- Independent workbook-integrity review and 79 focused tests passed. Prior validation remains 548 full offscreen tests, 40 CLI checks, compilation, diff and dependency audits; personal exports/profiles remain excluded.

## PR review cycle ledger

- Opened PR #29 as draft, then marked ready to start CI Verify. Base `62db9dc`, implementation head `f4554bd`; no merge conflicts.
- Requested Codex review with the skill helper: issue comment `6534620526`. First poll showed no response; the next showed the bot running on `f4554bd` with no inline threads yet. No actionable Codex comments are available at this checkpoint.
- Initial CI Verify run `41136707601` skipped while draft; ready-for-review run `41136762468` is in progress. No CI failure observed, so no production/test edits were made during this review pass.
- Brooks and the independent integrity pass found no actionable concerns. This checkpoint saves only the required review record/history. Request final-head Codex review and wait for terminal CI after pushing it.
- Keep final hosted review/check outcomes in the PR description so a status-only documentation commit does not invalidate the reviewed head. Leave the PR unmerged.
