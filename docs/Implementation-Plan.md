# Plan

Extend the verified Part 1 result-transfer baseline with a separate, prescription-specific Part 2 path that parses selected coach program blocks into a neutral review model before any MacroFactor workbook can be generated. Preserve the 0.3.0 safety contract from PR #10 (`11fd219`) and the dependency-audit hardening now on `origin/main` (`d3b8a23`), while recording that both PRs are merged and the prior implementation-plan status was stale.

## Scope
- In: Part 1 tracking reconciliation, direct-template discovery gate, prescription domain/config models, dynamic coach block/day/week discovery, conservative planned-prescription parsing, exact exercise mapping, configurable visible defaults, supersets/exclusions/custom warnings, CLI inspection and preview, JSON reporting, anonymized tests, documentation, issues, checkpoints, and a draft pull request.
- Out: an invented or unverified MacroFactor program schema, program `.xlsx` generation, MacroFactor compatibility claims, desktop Part 2 mode, Google Drive, private-service or phone automation, private workbook artifacts, and merging the feature branch.

## Action items
[ ] Reconcile Part 1 issues #1–#4 against implementation and test evidence, and replace stale PR #10/#11 status with a durable baseline summary.
[ ] Record the failed direct Export Program discovery gate and create an explicit blocker requesting that workbook before generator implementation.
[ ] Add a prescription-specific neutral domain model and backward-compatible Part 2 configuration for exact mappings, exclusions, custom-exercise warnings, supersets, and explicit defaults with provenance.
[ ] Discover selectable program blocks, repeated day sections, base prescription roles, and included week groups dynamically from OOXML without fixed sheet names, rows, or columns.
[ ] Parse only allow-listed prescription values, keep weekly plans separate from completed-result cells, preserve source text, and report missing, conflicting, optional, warmup, cardio, unsupported, or ambiguous instructions without guessing.
[ ] Add a Part 2 preview service and CLI mode that reports days, exercises, cycles, exact mappings, raw text, visible defaults, custom/unavailable exercises, skipped/blocking items, hashes, and a false generation-safety state while the template is unverified.
[ ] Add anonymized tests for shifted layouts, block/day/week selection, planned/result separation, supported parsing, raw retention, conflicts, defaults, exact mapping, exclusions, custom exercises, and ordered supersets while preserving Part 1 assertions.
[ ] Update README, local workflow guidance, CLI help, and the implementation plan to explain the manual import boundary, private-template workflow, and remaining generator/desktop validation gates.
[ ] Run targeted tests, `./scripts/test.sh`, source compilation, configuration parity, privacy/diff checks, and review the implementation against every conservative parsing risk.
[ ] Publish approved vertical-slice issues, save meaningful checkpoints and the final branch, and open a draft pull request without merging or marking Part 2 complete.

## Open questions
- None.
