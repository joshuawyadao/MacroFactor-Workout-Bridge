# Plan

Extend the verified Part 1 result-transfer baseline with a separate, prescription-specific Part 2 path that parses selected coach program blocks into a neutral review model and generates only structures proved by a direct MacroFactor Export Program workbook. Preserve the 0.3.0 safety contract from PR #10 (`11fd219`) and the dependency-audit hardening now on `origin/main` (`d3b8a23`).

## Scope
- In: the completed Part 2 preview foundation; read-only validation of the supplied direct export; an anonymized template fixture; dynamic template-schema inspection; template-aware preview hashes and blockers; conservative CLI generation for programs whose selected cycles have identical prescriptions, with guarded opt-in workout-row resizing; reconciliation against the earliest private coach block; OOXML integrity checks; tests, documentation, issue updates, and draft-PR checkpoints.
- Out: extrapolating a periodized multi-cycle layout not present in the verified export, unsupported set types or set-column expansion, MacroFactor compatibility claims before manual import, desktop Part 2 mode, Google Drive, private-service or phone automation, private workbook artifacts, and merging the feature branch.

## Action items
[x] Reconcile Part 1 issues #1–#4 against implementation and test evidence, and replace stale PR #10/#11 status with a durable baseline summary.
[x] Record the failed direct Export Program discovery gate and create an explicit blocker requesting that workbook before generator implementation.
[x] Add a prescription-specific neutral domain model and backward-compatible Part 2 configuration for exact mappings, exclusions, custom-exercise warnings, supersets, and explicit defaults with provenance.
[x] Discover selectable program blocks, repeated day sections, base prescription roles, and included week groups dynamically from OOXML without fixed sheet names, rows, or columns.
[x] Parse only allow-listed prescription values, keep weekly plans separate from completed-result cells, preserve source text, and report missing, conflicting, optional, warmup, cardio, unsupported, or ambiguous instructions without guessing.
[x] Add a Part 2 preview service and CLI mode that reports days, exercises, cycles, exact mappings, raw text, visible defaults, custom/unavailable exercises, skipped/blocking items, hashes, and a false generation-safety state while the template is unverified.
[x] Add anonymized tests for shifted layouts, block/day/week selection, planned/result separation, supported parsing, raw retention, conflicts, defaults, exact mapping, exclusions, custom exercises, and ordered supersets while preserving Part 1 assertions.
[x] Update README, local workflow guidance, CLI help, and the implementation plan to explain the manual import boundary, private-template workflow, and remaining generator/desktop validation gates.
[x] Run targeted tests, `./scripts/test.sh`, source compilation, configuration parity, privacy/diff checks, and review the implementation against every conservative parsing risk.
[ ] Publish the remaining vertical-slice issues after the proposed `to-issues` breakdown is approved.
[x] Save the feature branch and open draft PR #13 without merging or marking Part 2 complete.
[x] Verify the newly supplied workbook as a direct MacroFactor Export Program file and inspect it read-only without retaining private names or values.
[x] Add a neutral template-schema model and inspector that discovers metadata, block/cycle headers, workout row groups, set columns, and formatting capacity without fixed cell coordinates.
[x] Add an anonymized synthetic template fixture that preserves only the minimum verified structural contract and contains no private names, notes, mappings, or metadata.
[x] Make Part 2 preview accept a template, report before/after template hashes, and block mismatched day/exercise shapes, excess set counts, unsupported set types, custom/unavailable exercises, or differing selected-cycle prescriptions.
[x] Add a CLI generator that copies the template to a new path, replaces only validated program cells, rebuilds shared strings without stale template data, keeps both inputs unchanged, and validates all unrelated OOXML members byte-for-byte.
[x] Add targeted tests for schema validation, homogeneous-cycle generation, template/source immutability, output non-overwrite, shared-string cleanup, structural round-trip inspection, and every generation blocker.
[x] Update README, local workflow guidance, and CLI help with the verified scope and the remaining periodized/manual-import gates. Update issue #12 and draft PR #13 after saving the checkpoint.
[x] Run focused tests, `./scripts/test.sh`, compilation, configuration parity, source/template hashes, privacy checks, and final diff review before saving and pushing the checkpoint.
[x] Treat the coach `Style` field as preserved coach classification text and interpret it as a MacroFactor set type only when it exactly matches an allow-listed set-type alias.
[x] End each discovered day table at the first structurally blank separator after its first exercise so trailing goals, notes, reference tables, or other non-program sections are not parsed as exercises.
[x] Accept unambiguous `N to M` rep ranges, including an optional `rep`/`reps` suffix, while continuing to retain and block ambiguous prose.
[x] Add anonymized regression tests for coach classification labels, blank-separated trailing reference content, and plain-language rep ranges without weakening the existing safety assertions.
[x] Regenerate the private first-block review with the confirmed left-plan/right-result direction, verify both private workbook hashes remain unchanged, and keep the report and personal configuration ignored and uncommitted.
[x] Update user-facing documentation, run the focused and canonical validation suites, review the privacy boundary and diff, then save and push the checkpoint to the feature branch.

## Open questions
- None.

## Earliest-block conversion policy

The user clarified that chronological selection starts with the last worksheet and moves right to left. Exercise category and detailed variation must both remain available for exact mapping; the coach side of each weekly pair is planned input. Keep all days and optional exercises, honor explicit supersets, and exclude warmups and cardio. Use standard sets by explicit default, upper-bound rest ranges, no invented RIR, deferred rep targets for `Read week`, and full coaching detail in exercise notes. Unknown exercise identities, ambiguous set counts, special set encodings absent from the direct export, and unproved layouts remain concrete generation blockers.

[x] Discover separate category/variation roles and safely inherit a block-wide week header across matching day tables; expose right-to-left worksheet ordering.
[x] Add opt-in conversion settings for standard-set defaults, upper rest ranges, blank targets, coaching notes, and warmup/cardio exclusions while preserving strict and Part 1 behavior.
[x] Preserve all base/weekly coaching detail and explicit special-set instructions, use variation for exact mapping context, and keep unresolved identities/set counts visible.
[x] Verify blank active-set rep/RIR/rest cells in the direct export and support that structural contract in the generator with anonymized round-trip tests.
[x] Add opt-in resizing of existing workout row groups, rejecting reference-bearing or irregular templates; preserve header/set-column structure, styles, source bytes, and unrelated OOXML parts with structural round-trip tests.
[x] Preview the earliest worksheet under the approved policies and produce an ignored private decision list with proposed exact exercise names found in local history; do not use completed results as prescription data or apply unconfirmed mappings.
[ ] Generate the first candidate after exercise identities and ranged set counts are confirmed and a direct export demonstrates required special-set encoding. No actual coach-program candidate has yet been generated or manually imported.
[x] Run targeted tests, the canonical suite, compilation and privacy/diff checks; update README and local workflow documentation.
[x] Save the feature branch checkpoint with the policy/resizing validation evidence; leave the draft PR and manual-import gate open.

## Baseline and tracking
- PR #10 merged as `11fd219`, establishing Part 1 version 0.3.0 with its recorded 75-test, compile, diff, app-build, signature, and smoke verification.
- `origin/main` advanced during discovery to `d3b8a23` through merged PR #11. That dependency-audit-only change raised the pre-Part-2 collected test count to 76 without changing application behavior.
- Issues #1–#4 were reviewed acceptance criterion by acceptance criterion, received public completion evidence, and were closed after the current canonical suite passed.
- A verified direct MacroFactor Export Program workbook is now available as a private read-only input. Its package contains a dedicated program worksheet, program metadata, one block/cycle table, merged workout row groups, exercise/skipped/notes fields, and repeated per-set type/rep-range/RIR/rest columns.
- The verified export repeats one distinct cycle layout. It does not prove the OOXML layout for different prescriptions in different cycles, so periodized generation remains blocked pending a richer direct export or manual evidence.

## Verification
- `PYTHONPATH=src python3 -m unittest tests.test_program_generation tests.test_program_preview -v`: 20 passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v`: 96 passed with 2 optional GUI tests skipped because the direct interpreter lacks PySide6.
- `./scripts/test.sh`: all 96 tests passed, including the offscreen GUI tests.
- A disposable, synthetic 4-day program was written through the private verified export and structurally re-inspected: 538 target cells round-tripped, no unrelated OOXML member changed, both private input hashes remained stable, and the temporary output was removed.
- Independent final review added bidirectional set-type/superset consistency checks, unique set-header validation, required OOXML relationship/content-type/style validation, conservative rejection of rich shared strings that cannot be preserved safely, and blocking error handling for malformed worksheet XML.
- `python3 -m compileall -q src tests packaging`, example/package configuration parity, source/template hash checks, privacy review, and branch diff checks passed.
- The first private coach-block preview was regenerated with the confirmed planned/result direction. Both input hashes remained stable, the direct template schema was recognized, private reports and configuration remained ignored, and generation stayed blocked rather than guessing through unresolved review items.
- `./scripts/test.sh`: all 99 tests passed after adding the classification, table-boundary, and plain-language rep-range regressions. Compilation, configuration parity, ignored-path checks, and `git diff --check` also passed.
- Policy/resizing checkpoint: 40 targeted Part 2 tests and all 116 canonical tests passed, including Part 1 and GUI coverage. Added 17 anonymized policy tests without weakening existing assertions.
- A disposable synthetic program with resized workout groups round-tripped 282 target cells through the private direct export; no unrelated OOXML members changed. The source/template hash checks passed, and private previews, configuration, and decision notes remain ignored and uncommitted.
- Compilation, example/bundled configuration parity, `git diff --check`, and ignored-path checks passed for the policy/resizing checkpoint. The real export proves blank active-set targets and exercise notes, but not myo/drop encoding or differing cycle layouts; manual MacroFactor import remains unverified.

## Checkpoints
- `7c13560`: implemented and documented the gated Part 2 parser, neutral model, exact mapping/default review, CLI preview, and anonymized tests.
- `4bc8aba`: recorded validation evidence, reconciled tracking, and opened the reviewable draft.
- `f7c1682`: tightened result-column isolation, report non-overwrite behavior, superset completeness, mapping status, selected-cycle labels, and exercise ordering.
- `ca68a77`: added verified template inspection, conservative homogeneous-cycle generation, OOXML integrity checks, synthetic fixtures, tests, and documentation.
- Draft PR #13 contains the reviewable parser and generator checkpoints and remains blocked by the periodized-template and manual-import gaps recorded on issue #12.
