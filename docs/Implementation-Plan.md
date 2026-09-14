# Plan

Extend the verified Part 1 result-transfer baseline with a separate, prescription-specific Part 2 path that parses selected coach program blocks into a neutral review model before any MacroFactor workbook can be generated. Preserve the 0.3.0 safety contract from PR #10 (`11fd219`) and the dependency-audit hardening now on `origin/main` (`d3b8a23`), while recording that both PRs are merged and the prior implementation-plan status was stale.

## Scope
- In: Part 1 tracking reconciliation, direct-template discovery gate, prescription domain/config models, dynamic coach block/day/week discovery, conservative planned-prescription parsing, exact exercise mapping, configurable visible defaults, supersets/exclusions/custom warnings, CLI inspection and preview, JSON reporting, anonymized tests, documentation, issues, checkpoints, and a draft pull request.
- Out: an invented or unverified MacroFactor program schema, program `.xlsx` generation, MacroFactor compatibility claims, desktop Part 2 mode, Google Drive, private-service or phone automation, private workbook artifacts, and merging the feature branch.

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

## Open questions
- None.

## Baseline and tracking
- PR #10 merged as `11fd219`, establishing Part 1 version 0.3.0 with its recorded 75-test, compile, diff, app-build, signature, and smoke verification.
- `origin/main` advanced during discovery to `d3b8a23` through merged PR #11. That dependency-audit-only change raised the pre-Part-2 collected test count to 76 without changing application behavior.
- Issues #1–#4 were reviewed acceptance criterion by acceptance criterion, received public completion evidence, and were closed after the current canonical suite passed.
- No verified direct MacroFactor Export Program workbook was found. Issue #12 tracks the required private template and anonymized-fixture gate; generator and compatibility work remain blocked.

## Verification
- `PYTHONPATH=src python3 -m unittest tests.test_program_preview -v`: 13 passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests`: 89 passed with 2 optional GUI tests skipped because the direct interpreter lacks PySide6.
- `./scripts/test.sh`: all 89 tests passed, including the offscreen GUI tests.
- The final safety review added explicit plan/result direction, exclusive report creation, reserved-path protection, complete contiguous superset validation, exact unmatched availability status, canonical selected-cycle labels, and per-day exercise ordering.
- `python3 -m compileall -q src tests packaging`, example/package configuration parity, privacy review, and branch diff checks passed.

## Checkpoints
- `7c13560`: implemented and documented the gated Part 2 parser, neutral model, exact mapping/default review, CLI preview, and anonymized tests.
- `4bc8aba`: recorded validation evidence, reconciled tracking, and opened the reviewable draft.
- Final review checkpoint: tightened result-column isolation, report non-overwrite behavior, superset completeness, mapping status, selected-cycle labels, and exercise ordering.
- Draft PR #13 contains the reviewable Part 2 checkpoint and remains blocked by issue #12 plus manual import validation.
