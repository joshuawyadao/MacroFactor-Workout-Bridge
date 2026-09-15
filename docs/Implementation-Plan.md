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
- None for this slice. The user approved equal lower/upper targets for exact rep counts and blank structured targets for minimum-only prescriptions, retaining the original minimum text in exercise notes for manual entry. This is an explicit fallback, not native minimum-only encoding support.

## Program appearance and target-format follow-up

The latest reference was inspected read-only using spreadsheet tooling and the production OOXML reader. Its rep-range cells contain bounded equal targets, with no formulas or separate unbounded field. It does not resolve native minimum-only encoding. Its metadata independently confirms the existing Red and Rocket values. Choose those values for growth-oriented programs in the private configuration; preserve template metadata by default for other users and do not infer an unsupported color/icon catalog.

[x] Inspect the new reference values and a rendered target range, verify its hash is unchanged, and distinguish the observed bounded encoding from the requested minimum-only semantics.
[x] Resolve the rep-target fallback with the user: exact N becomes N–N; N+ remains in notes with blank targets. Add an opt-in notes-only minimum policy, retain strict blocking by default, and never alter the original coach source.
[x] Add optional program color/icon configuration and preview provenance. Discover unique metadata cells dynamically, write only verified values, and preserve template defaults when no override is configured.
[x] Add synthetic tests for metadata preservation/overrides, invalid or ambiguous metadata, rep fallback provenance and notes, output integrity, immutable inputs and non-overwrite. Keep native minimum-only support gated and preserve existing assertions.
[x] Apply the approved target policy and chosen appearance to ignored configuration, then generate and structurally inspect one distinct corrected candidate through the production CLI.
[x] Update README, local workflow guidance and this plan; run 86 targeted tests, all 162 canonical tests, compilation and privacy/diff checks.
Final save: use `save-branch` to commit and push only the feature branch, update the existing blocker/draft PR with redacted evidence, and request a manual import test without merging or claiming completion.

## Manual-import feedback correction slice

The user has reported content defects after testing the first candidate: insufficient duration, blank rep targets, redundant notes, a set-count correction, and missing exercises. This is useful manual-test evidence, not acceptance of the generated program. The prior structural tests do not establish semantic fidelity inside MacroFactor. Keep PR #13 draft and issue #12 open. The clarification pause is resolved: use base-table prescriptions repeated across selected weeks, retain weekly updates separately for review, preserve the confirmed imported identity, and apply the explicit inclusion choices privately. Do not claim periodization or minimum-only output support without direct evidence.

[x] Inspect the relevant coach prescription cells, both direct program references and the original candidate read-only; distinguish planned columns from completed results and verify all four files remain byte-for-byte unchanged.
[x] Confirm that the original candidate contains the reported canonical-name discrepancy, that category-based warmup exclusion omitted other requested rows, and that the references contain bounded or blank rep targets but no minimum-only example. Keep all identifying evidence private.
[x] Resolve the open questions and update this plan before implementation. Treat the latest explicit inclusion and count corrections as reviewed Part 2 overrides, never edits to the coach workbook or Part 1 mappings.
[x] Add an opt-in base-table prescription mode: selected weeks determine repeated cycle count, while weekly coach text remains separate review data and cannot supply targets, set types, mapping context or exclusions. Preserve strict weekly mode by default.
[x] Discover a unique designation below each day heading in the same dynamically located column. Preserve the original day identifier and full designation in review; use the designation for export names, falling back safely when missing or ambiguous. Cover shifted columns, merged headings, fractional days and multiple blocks.
[x] Extend the neutral model and conservative parser for per-set rep lists, explicitly understood unilateral suffixes, and minimum-only targets. Preserve raw text, set-count/list-length checks, weekly conflicts and visible provenance; do not turn arbitrary numeric prose or date serials into targets.
[x] Add exact-rule, reviewed corrections for ambiguous source values and narrow inclusion exceptions, with preview warnings showing when a correction differs from the source. Preserve global warmup/cardio exclusions elsewhere.
[x] Separate concise exported exercise notes from full raw review data. Keep meaningful tempo, equipment, unilateral, progression and unsupported instructions without redundant field dumps; preserve the existing detailed-notes option and its safety behavior.
[x] Implement the user-approved repeated-base workflow without inferring differing-cycle encoding. Keep native minimum-only output blocked until a direct reference proves it; the subsequent approved notes-only fallback is separate.
[ ] Verify native minimum-only encoding if direct native support is pursued later. The approved notes-only fallback removes this prerequisite for the current candidate, without claiming native support.
[x] Add anonymized regression coverage in the program preview, policy, generation and mixed-set tests for per-set reps, unilateral targets, minimum-only gating, corrections, inclusion exceptions, concise notes, cycle duration and exact output identities. Preserve all existing assertions and Part 1 behavior.
[x] Update README, local workflow documentation, CLI help where applicable, and this plan with the new policies, verified scope and remaining manual-test gaps.
[x] Run 76 targeted Part 2 tests and all 152 canonical tests, compilation, configuration parity and diff/privacy checks. Synthetic generation tests verify per-set targets, repeated-cycle metadata, day names, immutable inputs and non-overwrite. All three private input hashes and the prior candidate still match the saved evidence.
[x] Generate a distinct private corrected candidate using the approved notes-only minimum fallback; leave the existing candidate unchanged.
Final handoff: save and push the validated feature-branch correction checkpoint with `save-branch` and update tracking with redacted evidence. The replacement candidate now needs manual import/content confirmation; do not merge or mark Part 2 complete.

## Verified mixed-set candidate

A second direct program export demonstrates one standard set followed by two `Myo Set` values, with blank targets. Its all-blank rep targets omit rep-range columns entirely. Use that file only as read-only encoding evidence; retain the earlier full-layout export as the generation template. Do not expand support to sparse template layouts, drop sets, or periodization in this slice.

[x] Add ordered per-set type fields to the prescription model and explicit, exact-rule Part 2 configuration for the approved mixed-type sequence and blank rep targets; preserve raw coach instructions and policy provenance.
[x] Write only the proved standard/myo labels into the existing template set columns, checking sequence length, coach conflicts, unsupported types, supersets, and cycle consistency before generation.
[x] Add minimal synthetic mixed-type fixtures and regression tests for blank targets, preview visibility, round trips, immutability, non-overwrite, conflict and invalid-configuration gates; preserve all existing assertions.
[x] Apply the approved policy to the private exact mapping, generate a distinct earliest-block first-cycle candidate through the CLI, inspect its output and all input hashes, and leave manual MacroFactor import unverified.
[x] Update README, local workflow guidance and this plan, run targeted/canonical tests, compilation and privacy/diff checks, and save the feature-branch checkpoint without private artifacts. Keep PR #13 draft and issue #12 open for remaining validation.
[ ] Receive manual import confirmation, including exercise identities, mixed set types, blank targets, notes and preserved workout structure. Do not mark Part 2 complete or merge before that validation.

## Earliest-block conversion policy

The user clarified that chronological selection starts with the last worksheet and moves right to left. Exercise category and detailed variation must both remain available for exact mapping; the coach side of each weekly pair is planned input. Keep all days and optional exercises, honor explicit supersets, and exclude warmups and cardio. Use standard sets by explicit default, upper-bound rest ranges, no invented RIR, deferred rep targets for `Read week`, and full coaching detail in exercise notes. Unknown exercise identities, ambiguous set counts, special set encodings absent from the direct export, and unproved layouts remain concrete generation blockers.

[x] Discover separate category/variation roles and safely inherit a block-wide week header across matching day tables; expose right-to-left worksheet ordering.
[x] Add opt-in conversion settings for standard-set defaults, upper rest ranges, blank targets, coaching notes, and warmup/cardio exclusions while preserving strict and Part 1 behavior.
[x] Preserve all base/weekly coaching detail and explicit special-set instructions, use variation for exact mapping context, and keep unresolved identities/set counts visible.
[x] Verify blank active-set rep/RIR/rest cells in the direct export and support that structural contract in the generator with anonymized round-trip tests.
[x] Add opt-in resizing of existing workout row groups, rejecting reference-bearing or irregular templates; preserve header/set-column structure, styles, source bytes, and unrelated OOXML parts with structural round-trip tests.
[x] Preview the earliest worksheet under the approved policies and produce an ignored private decision list with proposed exact exercise names found in local history; do not use completed results as prescription data or apply unconfirmed mappings.
[x] Generate the first candidate after exercise identities and ranged set counts are confirmed and a direct export demonstrates required special-set encoding. The candidate is generated privately; manual import is still pending.
[x] Run targeted tests, the canonical suite, compilation and privacy/diff checks; update README and local workflow documentation.
[x] Save the feature branch checkpoint with the policy/resizing validation evidence; leave the draft PR and manual-import gate open.

## Baseline and tracking

### Approved set ranges and mappings

The user approved upper-bound set counts and the private exercise-match proposals. Implement an opt-in upper-bound base set-count policy with visible provenance and retained raw ranges, and apply approved identities only in ignored Part 2 configuration. The completed-result `+` notation is not evidence of native program myo-set encoding; the subsequent direct-export evidence resolves that gate for explicit standard/myo sequences only.

[x] Add strict-by-default base set-count range handling; preserve exact weekly conflicts, malformed-value blockers, and template capacity checks.
[x] Add anonymized parsing, provenance, conflict, capacity, and output round-trip tests without changing existing assertions.
[x] Apply the approved private mappings separately from the Part 1 configuration, regenerate preview, and verify the remaining gate and unchanged input hashes. Only unsupported special-set encoding remains blocking for the selected first-cycle candidate.
[x] Update README/local workflow guidance and run targeted/canonical tests, compilation, configuration parity and privacy/diff checks; save the validated feature-branch checkpoint without private inputs or mappings.

### Historical baseline
- PR #10 merged as `11fd219`, establishing Part 1 version 0.3.0 with its recorded 75-test, compile, diff, app-build, signature, and smoke verification.
- `origin/main` advanced during discovery to `d3b8a23` through merged PR #11. That dependency-audit-only change raised the pre-Part-2 collected test count to 76 without changing application behavior.
- Issues #1–#4 were reviewed acceptance criterion by acceptance criterion, received public completion evidence, and were closed after the current canonical suite passed.
- A verified direct MacroFactor Export Program workbook is now available as a private read-only input. Its package contains a dedicated program worksheet, program metadata, one block/cycle table, merged workout row groups, exercise/skipped/notes fields, and repeated per-set type/rep-range/RIR/rest columns.
- The verified export repeats one distinct cycle layout. It does not prove the OOXML layout for different prescriptions in different cycles, so periodized generation remains blocked pending a richer direct export or manual evidence.

## Verification
- Appearance/notes-only checkpoint: all 162 canonical tests and 86 targeted Part 2 tests pass, including 10 new anonymized regressions. Exact reps stay bounded; approved minimum-only fallback preserves notes and raw provenance with blank targets. Tests cover default blocking, defaults/conflicts, mixed-set blank overrides, note modes, verified appearance values, shifted/missing/ambiguous metadata, input immutability, unrelated OOXML preservation and output non-overwrite. Compilation, configuration parity and privacy/diff checks passed. A distinct corrected private candidate passed structural and independent expected-target checks; all four input hashes and the previous candidate hash remain unchanged. Read-only spreadsheet inspection confirmed metadata and representative targets/mixed types. Manual import remains unverified for the corrected candidate.
- Manual-feedback correction checkpoint: all 152 canonical tests and 76 targeted Part 2 tests passed, including 22 new tests in `tests/test_program_corrections.py`. Coverage includes base/weekly separation, repeated duration, per-set reps, unilateral and minimum-only targets, exact-source corrections, concise notes, warmup inclusion, dynamic day designations and output integrity. Compilation, configuration parity, privacy and diff checks passed. The private corrected preview has one remaining minimum-only encoding gate; no replacement workbook is claimed. All three original input hashes and the first candidate hash remain unchanged.
- Mixed-set checkpoint: 54 targeted Part 2 tests and all 130 canonical tests passed. Eight new anonymized tests cover native labels, ordered sequences, blank targets, CLI/report visibility, immutable-input/non-overwrite round trips, sequence length/conflicts, invalid configuration, differing-cycle order and independent RIR safety. Existing assertions remain unchanged.
- The first private CLI-generated candidate passed a fresh 482-cell structural round trip against the current code. The coach source, full-layout template and mixed-set reference all retained their hashes. Native mixed types, blank rep/RIR cells, full coach notes, and unchanged unrelated OOXML members were checked. Output, evidence, reports and mappings remain ignored and uncommitted. Manual import is pending; no compatibility claim is made.
- Compilation, example/bundled configuration parity, ignored-path checks and `git diff --check` passed for this checkpoint. Spreadsheet tooling was used only for read-only reference inspection; production remains Python/OOXML.
- Approved-range checkpoint: 46 targeted Part 2 tests and all 122 canonical tests passed. Six additional anonymized tests cover upper-count provenance and round trips, malformed ranges, weekly conflicts, exact weekly provenance, template capacity, and invalid configuration. Input hashes, compilation, configuration parity, privacy and diff checks passed. No actual program candidate or manual import is claimed.
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
- Draft PR #13 contains the reviewable parser and generator checkpoints and awaits corrected-candidate manual validation on issue #12. Differing-cycle layouts and native minimum-only encoding remain future schema limits, not prerequisites for the approved repeated-base, notes-only workflow.
