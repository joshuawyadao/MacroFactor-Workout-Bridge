# Plan

Harden the existing local workbook workflows against the six confirmed checkup findings, starting with reviewed-input validity, safe publication, standalone program coverage and protected report destinations, then numeric validation and consistent block attribution. Preserve current history consolidation, exact mappings, independent audits, source immutability and the manual MacroFactor import requirement.

## Scope
- In: checkup findings MWB-001 through MWB-006; focused synthetic regressions; existing Python/OOXML/Qt workflows; README and local workflow documentation; verified local commit checkpoints and final branch push.
- Out: broader UI refactoring, CLI EOF cleanup, dependency upgrades, private source/configuration edits, historical-export reselection policy, installed application replacement, live MacroFactor import, issue/PR creation and merge.

## Action items
[x] Confirm clean baseline d4cf5de, review README, CONTRIBUTING, Local-File-Workflow and Regression-Validation, and map existing integration/program/GUI/history tests. The unchanged baseline passed all 444 tests with no skips in 93.267 seconds.
[x] Obtain explicit approval to create codex/safety-checkup from the current checkout and implement, validate, commit and push this scope; checkpoint the resolved plan before implementation.
[x] Bind Part 1 previews to workbook/export contents and effective Part 1 mapping semantics, including re-reading the original mapping path, and reject changes before writing; preserve the existing requirement that program-only config edits do not alter Part 1 previews. Cover in-place edits, mapping changes, preview-time drift and unchanged-input success.
[x] Write Part 1 candidates to temporary sibling files, verify protected inputs and OOXML integrity, then publish without replacing a destination; cover rejected validation, partial writes, input drift and late collisions.
[x] Add an independent authored-row coverage gate in program_audit, invoked by standalone previews in base and selected-week modes without requiring complete week coverage; pass an optional reviewed reference marker through preview before batch's full audit, preserve intentional week subsets, and rehash the source after the extra read.
[x] Share exclusive report destination protection across desktop and CLI, reserving source inputs, mapping and generated workbook; test aliases, existing reports and late destination collisions.
[x] Reject nonfinite transferable Part 1 values with visible diagnostics, preserving raw history inspection; cover NaN, signaling NaN and both infinities in reps/weight and avoid false empty-day markers.
[x] Centralize block mapping validity in a pure history helper used before interval assignment and by progress/comparison/explorer/default selection. Require a Monday start, nonempty case-insensitively unique week labels and no overlap; detect overlap before filtering so both ranges remain invalidated. Preserve editable annotations, caller-specific diagnostics and raw calendar history.
[x] Update README and Local-File-Workflow with the strengthened preview/publication/report contracts and consistent mapping behavior; record validation evidence here without claiming private-data or manual-import acceptance.
[x] Run focused tests per slice, independent workbook-integrity review, the complete ./scripts/test.sh suite, source compilation, configuration parity, source GUI smoke, diff checks and the documented dependency audit if available or safely provisioned; commit coherent checkpoints and push the completed branch using save-branch.

## Open questions
- None. Branch creation and the implementation/save workflow are explicitly approved. Report saving will require a distinct new file, matching the existing CLI policy. Unsupported or unaccounted program rows remain blocked rather than guessed.

## Validation evidence
- First four fixes: 53 combined transfer/report/GUI/integration/expansion tests passed; all 251 program tests passed. Independent workbook-integrity review confirmed the safety paths and identified malformed mapping JSON shape handling, now covered and corrected. Full-suite verification follows the numeric/block slice.
- Numeric/block slice: 45 numeric/formatting/transfer/integration tests and 61 history/projection/GUI tests passed. Independent review confirmed numeric withholding and shared attribution, with a follow-up regression removing an invented interval for blocks without weeks and an actual mixed valid/invalid workbook-apply assertion.
- Initial integrated run: all 484 tests passed, zero skips, in 49.765 seconds. Final run including the zero-week regression: all 485 tests passed, zero skips, in 60.438 seconds (exit 0). Compilation, bundled/example configuration parity and diff checks passed. The documented hash-pinned audit ran in an isolated Python 3.11 temporary environment and found no known vulnerabilities in all three dependency locks.
- Source GUI smoke passed for version 0.9.1 with offscreen Qt. No installed bundle was rebuilt or replaced; private workbook acceptance and manual MacroFactor import remain outside this validation.

## Changed regression coverage
- Added `tests/test_transfer_safety.py`, `tests/test_report_safety.py`, `tests/test_program_source_coverage.py`, `tests/test_numeric_transfer.py` and `tests/test_block_mapping.py`. Extended `tests/test_program_configured_cycles.py` and `tests/test_comparison_gui.py`.

## Save checkpoints
- `46aa645`: resolved plan before implementation.
- `d9a9249`: reviewed-input binding, staged output publication, program source coverage and protected report saving.
- Final numeric/block validation checkpoint completes this plan on `codex/safety-checkup`; save the complete branch to `origin` without creating or merging a pull request.

## PR #22 publication compatibility follow-up

Codex review identified that hard-link-only publication prevents valid Part 1 transfers to filesystems such as exFAT or network mounts. Add an exclusive-create fallback for unsupported hard-link operations after candidate validation. Track the identity of the created output so partial-copy, input-drift and validation failures remove only this attempt's file; preserve late competing files and keep input snapshots authoritative. Existing hard-link publication remains the preferred atomic path.

- [x] Reproduce unsupported-hard-link failure and add successful fallback, late-collision, partial-copy and protected-input-drift regressions.
- [x] Implement the bounded Part 1 fallback and document its publication behavior.
- [x] Run focused transfer tests and the complete suite; prepare the fix for save/push. Hosted CI Verify and the post-push acknowledgment of Codex comment 4125399517 are tracked in PR #22.

Open questions: none. This narrow compatibility fix is authorized by the requested PR review cycle; no source files, overwrite policy or program-generation behavior are changed.

Follow-up focused validation: all 40 transfer/numeric/integration tests passed, including five new fallback cases. The unsupported-link cases failed before the fix. Full-suite and hosted verification follow.

Follow-up final local validation: all 490 tests passed with no skips in 59.760 seconds; compilation and diff checks passed. Review also confirmed candidate identity is captured before linking. The existing portable check/unlink cleanup race and fallback copy visibility are documented in Local-File-Workflow.md; no platform-specific coordination was introduced.

## Per-side transfer calibration

Calibrate the private Part 1 transfer mapping using existing exact aliases and per-exercise weight conversion. Add anonymized end-to-end regressions and document weight versus repetitions.

### Scope
- In: active private mapping, six confirmed per-side rules, exact substitutions, synthetic tests, transfer documentation.
- Out: Part 2 configuration, workbook edits, machine labels, base weight, generic inference, formatter redesign, app rebuild.

### Action items
[x] Inspect README, local-file workflow, configuration, formatter, matching and tests.
[x] Checkpoint the plan on the approved branch.
[x] Back up and update the active private mapping while preserving existing aliases and excluding private data from Git.
[x] Add synthetic preview/apply regressions for six per-side rules, unchanged reps, substitutions, zero load, total-load exercises and occupied-cell protection.
[x] Document per-side weights and unchanged repetitions in README and local-file workflow.
[x] Validate mappings against the labeled workbook without altering it; run targeted and broader tests and diff checks.
[x] Prepare final branch save; private configuration is backed up and installed separately.

### Open questions
- None. Branch and six weight conversions are confirmed; repetitions remain unchanged.

### Validation
- All 18 reviewed exercises match unique intended workbook rows; six half-weight/suffix rules and twelve unchanged-load rules verified.
- Targeted transfer/formatting/calibration/integration suite: 28 tests passed.
- Canonical suite (`./scripts/test.sh`): 445 tests passed, no skips.
- Compilation and `git diff --check`: passed.
- Private configuration was backed up before installation. No workbook edits, Part 2 configuration edits or app rebuild were needed.

### PR readiness follow-up

Preserve main’s completed safety-hardening record and this branch’s calibration record. Restart the installed app, verify the selected private mapping, run an isolated synthetic transfer preview, and rerun validation against merged main. Keep private files out of the PR.

- [x] Resolve the implementation-plan conflict by retaining both completed work records.
- [ ] Complete native app and current-head test verification.
- [ ] Complete Brooks review, Codex review, hosted CI and final mergeability checks.

Open questions: none.
