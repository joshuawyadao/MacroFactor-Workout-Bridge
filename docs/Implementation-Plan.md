# Plan

Make completed-set formatting omit a repeated weight when regular sets lead into a myo set at the same load. Preserve mini-set notation, explicit weight changes and workbook-transfer safeguards, and verify that corrected reps continue to come directly from a fresh source export.

## Scope
- In: formatting.py, synthetic formatter and workbook-transfer regressions, result-formatting guidance in docs/CLI-Reference.md, local checkpoints and a pushed feature branch.
- Out: private exports/workbooks/mappings, automatic rep corrections, inferred exercise replacements, warm-up copying, program-generation behavior, dependency changes, app installation and pull request creation.

## Action items
[x] Trace the shared formatter, export importer and transfer path; read docs/Development.md, docs/CLI-Reference.md and existing formatting/integration coverage.
[x] Create codex/compact-myo-results from this worktree's current commit and checkpoint the resolved plan.
[x] Add synthetic regressions for regular-to-myo same-load grouping, per-side conversion, changed loads and boundaries after drop/myo series; cover preview and saved workbook output.
[x] Update the myo activation formatter to reuse the preceding regular-set weight group only when its load is unchanged.
[x] Document the compact format and fresh-export requirement for corrected source reps in docs/CLI-Reference.md.
[x] Run focused tests, the canonical offscreen suite, compilation, dependency audit and diff checks; record results and inspect the final diff.
[x] Commit the completed change and plan, then push the feature branch with task files only.

## Open questions
- None. Corrected rep counts are source data and must never be guessed or hard-coded. Existing behavior for a regular set after a myo series remains unchanged.

## Validation and checkpoints
- Plan checkpoint: `4170075` on `codex/compact-myo-results`.
- Regression reproduction: four new assertions failed against the old duplicate-weight formatter. After the change, all 56 focused formatting, integration, numeric-transfer and transfer-safety tests passed.
- Canonical source/offscreen GUI suite: 497 tests passed in 82.741 seconds, no skips, exit 0. Compilation and diff checks passed.
- Independent workbook-integrity review found no correctness issue. Its suggested regular-after-joined-myo boundary is now covered by an additional assertion in the existing test; all 15 formatter tests passed afterward.
- The synthetic integration case confirms compact text in preview and saved output, unchanged input hashes and no unrelated workbook ZIP changes.
- Dependency audit completed after retrying the initial network restriction. It returned exit 1 for three existing advisories in the audit-tool-only `urllib3==2.7.0` pin in `requirements/audit.lock`: `PYSEC-2026-4177`, `PYSEC-2026-4176` and `PYSEC-2026-4175`. The tool reports 2.8.0 as the fixed version. Dependency upgrades remain outside this formatter change; all lock files are unchanged.
- CLI result-formatting documentation now explains compact regular-to-myo grouping and the need for a fresh export after correcting source reps. No app rebuild or install was performed.
- Only the formatter, two synthetic test modules and the two documentation files belong to this change. Private workout files and generated artifacts remain ignored.
