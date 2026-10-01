# Plan

Audit the repository documentation against current source, then turn the long README into an approachable entry point with focused guides and accessible workflow graphics. Preserve advanced policies and safety limits, validate the examples, and deliver incremental commits and a reviewed pull request.

## Scope
- In: README, documentation navigation, first-run and desktop guidance, CLI/configuration/program references, local-file workflow, architecture, contributor verification, troubleshooting, synthetic diagrams, and PR review.
- Out: application behavior, dependencies, private data or mappings, app rebuild/install, real MacroFactor import, and merging the PR. The previous per-side mapping branch remains separate; this branch starts at current `origin/main`.

## Action items
[x] Inspect existing docs, all source areas, packaging, test runner and CI; delegate independent program and workbook-safety documentation audits.
[x] Create `codex/documentation-guide-refresh` from `origin/main` and checkpoint this resolved plan.
[x] Rewrite README and add a documentation index, getting-started and desktop guides, CLI/configuration references, and accessible workflow graphics.
[x] Preserve and organize detailed program generation/batch policies; streamline Local-File-Workflow and add practical troubleshooting.
[x] Document module ownership, build/test/dependency maintenance and documentation conventions; update CONTRIBUTING and label historical validation evidence.
[x] Verify links/anchors, SVG rendering, command help and synthetic CLI examples; run canonical tests, compilation, dependency audit and diff checks. Update existing documentation-contract tests to follow the new canonical development guide; production behavior remains unchanged.
[x] Review input/output/privacy claims and advanced-policy coverage; commit each coherent documentation slice with validation evidence.
[x] Push the feature branch, open PR #23 and request review; track Codex feedback, hosted CI and mergeability on the PR through a terminal result without merging.

## Open questions
- None. Use source-controlled SVG and Mermaid diagrams with text equivalents, keep private screenshots and exports out of the documentation, and organize around users’ tasks.

## Validation and checkpoints
- User guides: synthetic fixture inspect/preview produced six expected writes with deliberate review cases; all local links/anchors and nine JSON examples parsed successfully. The workflow SVG was rendered and visually checked for clipping and readable contrast.
- Setup commands use non-overwriting `cp -n`; the private mapping is created before archive commands. CLI apply and program-preview exit semantics are explicit.
- Independent program and workbook-safety documentation audits are complete. Corrected audit boundaries, discovery/default settings, malformed-import limits, current-note provenance, superset limits and partial-transfer guidance.

- First canonical run: 490 tests in 78.551 seconds, exit 1; four subtest failures were existing documentation contracts looking for commands in README/CONTRIBUTING after their move. Preserve those command assertions in Development.md and add assertions that both entry pages link to that guide, then rerun focused and full checks. All executable-behavior tests passed; no production changes are needed.
- Dependency audit: all three hash-pinned locks passed with no known vulnerabilities. Compilation passed.

- Focused documentation/dependency checks: 16 tests passed in 6.344 seconds, exit 0. The existing runner and Python 3.11 audit assertions now target Development.md; a new test preserves navigation from README and CONTRIBUTING. No production code changed.
- All seven CLI subcommand help pages and workspace help passed. Temporary synthetic preview/apply/report/no-overwrite/input-hash checks and workspace setup/archive/status passed.
- Checkpoint `5bb3e28` saved the plan; `bb9e45a` saved the user-guide/graphics slice. The next checkpoint records contributor guidance and the completed source-accuracy review.

- Final canonical suite: **491 tests passed in 65.026 seconds**, no skips, exit 0. Compilation, source GUI smoke, 190 local links/anchors, nine JSON examples and diff checks passed. No app rebuild or personal-data acceptance was needed.
- Checkpoint `0135700` saved contributor guidance and documentation-contract coverage. All application modules are mapped; unchanged SECURITY.md and CODE_OF_CONDUCT.md remain the canonical policies.
- [PR #23](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/pull/23) contains all checkpoint commits. Codex review was requested. Its live review/check state and final readiness are tracked in the PR and completion report, not as a permanent guarantee in this plan.
- Brooks PR review: sampled the large documentation relocation and examined all changed test assertions; 100/100, stable, with no actionable findings. The large diff is a cohesive manual split with canonical topic pages, not unrelated code changes. Production dependency and domain structure are unchanged; the quick test-design scan is inapplicable to documentation-only behavior.

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

### Codex review correction

- [x] Correct the restart advice: Part 1 requires explicitly selecting the private mapping after restart; Dashboard mapping auto-loading is separate.
- [x] Preserve the new documentation layout from main and move per-side details to Configuration.md.
- Native synthetic preview and workbook save passed, including occupied-cell protection and workbook integrity. Restoring the real workbook was interrupted by an inaccessible app window and the Mac locking; full real-data verification remains incomplete.
- Pre-documentation-merge full suite: 491 tests passed, no skips. Brooks review found no actionable issues.
- Hosted CI is blocked by three audit findings against urllib3 2.7.0 inherited from main. The user subsequently approved the audit-lock update recorded below.

### Approved audit dependency update

The user approved updating the inherited urllib3 audit-tool dependency and confirmed the Mac is unlocked. Update only the audit lock to the reported fixed 2.8.0 release, verify the wheel against PyPI metadata, resolve/install the full hash-pinned closure on Python 3.11, run pip check and audit all three locks, then push and verify hosted CI and review readiness. Application/test dependency locks are unchanged, so an application rebuild would not exercise this audit-only change.

- [x] Update the approved dependency and verify the complete audit closure and all dependency audits.
- [ ] Validate dependency contract tests and final CI; preserve exact hashes and other pins.
- [x] Confirm the unlocked native app shows the real labeled coach workbook, private mapping, selected block and Week 1. No September 25 export remains at its supplied path; export selection stays empty.

Open questions: none.

Audit update validation: urllib3 2.8.0 universal-wheel SHA-256 matched official PyPI metadata and the downloaded wheel. The full hash-pinned Python 3.11 audit closure installed on Apple silicon; pip check passed and pip-audit found no known vulnerabilities across audit, build and test locks. The complete Linux x86-64 Python 3.11 wheel closure also downloaded successfully with required hashes. All 17 focused dependency/transfer tests and diff checks passed. Only the urllib3 pin and hash changed; no production or test dependency locks changed. Hosted CI and refreshed Codex review follow the push.
