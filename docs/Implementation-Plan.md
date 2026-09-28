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
[ ] Reject nonfinite transferable Part 1 values with visible diagnostics, preserving raw history inspection; cover NaN, signaling NaN and both infinities in reps/weight and avoid false empty-day markers.
[ ] Centralize block mapping validity in a pure history helper used before interval assignment and by progress/comparison/explorer/default selection. Require a Monday start, nonempty case-insensitively unique week labels and no overlap; detect overlap before filtering so both ranges remain invalidated. Preserve editable annotations, caller-specific diagnostics and raw calendar history.
[ ] Update README and Local-File-Workflow with the strengthened preview/publication/report contracts and consistent mapping behavior; record validation evidence here without claiming private-data or manual-import acceptance.
[ ] Run focused tests per slice, independent workbook-integrity review, the complete ./scripts/test.sh suite, source compilation, configuration parity, source GUI smoke, diff checks and the documented dependency audit if available or safely provisioned; commit coherent checkpoints and push the completed branch using save-branch.

## Open questions
- None. Branch creation and the implementation/save workflow are explicitly approved. Report saving will require a distinct new file, matching the existing CLI policy. Unsupported or unaccounted program rows remain blocked rather than guessed.

## Validation evidence
- First four fixes: 53 combined transfer/report/GUI/integration/expansion tests passed; all 251 program tests passed. Independent workbook-integrity review confirmed the safety paths and identified malformed mapping JSON shape handling, now covered and corrected. Full-suite verification follows the numeric/block slice.
