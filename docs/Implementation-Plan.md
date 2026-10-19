# Plan

Update the reviewed macOS build runtime from Python 3.11.2 to the patched Python 3.11.17 baseline, then audit the exact locked packages before selecting any package changes. Keep the Python minor version and hash-verified dependency closures coherent, rebuild the app, and validate synthetic workbook and desktop behavior.

## Scope
- In: Python build-runtime selection and preflight, CI runtime pin, dependency advisory checks and any confirmed fixes, dependency/build regression tests, README and canonical setup/development guidance, local app rebuild, commit checkpoints, branch push and the subsequently requested PR review cycle.
- Out: Python minor-version migration, unrelated package freshness updates, global interpreter replacement, personal workbooks/exports, app installation into Applications, merging.

## Action items
[x] Inspect README, docs/Development.md, docs/Getting-Started.md, manifests, all three locks, build/test scripts, CI and tests/test_build_dependencies.py; verify Python 3.11.17 upstream security release and an Apple-silicon runtime source.
[x] Resolve the detached-checkout save branch: the user selected codex/patched-python-runtime; checkpoint this plan before implementation.
[x] Provision an isolated, checksum-verified Python 3.11.17 runtime for this checkout, leaving the system interpreter available for rollback.
[x] Audit all exact locked dependencies; update only packages with confirmed security/reliability fixes and preserve closure/hash consistency.
[x] Require patched Python 3.11 for macOS packaging before environment recreation; pin CI to the reviewed patch, separate test environments by patch and interpreter identity, and update setup/development docs.
[x] Extend build-dependency tests for rejected old/prerelease/wrong-minor interpreters, accepted patched versions, and failure before build-environment mutation.
[x] Run focused tests, full offscreen tests, all-lock advisory audit, pip check, compilation, macOS build/signature and bundled-runtime smoke checks using the patched interpreter; use only synthetic data.
[x] Integrate the independent workbook-safety review, record validation and rollback details, and prepare the validated implementation for final commit and push on the selected branch.

## Open questions
- None. The user approved codex/patched-python-runtime. PyPI advisory data confirms urllib3 2.7.0 in audit.lock needs the 2.8.0 security fixes (GHSA-8988-9cw3-xx77, GHSA-gh4c-6fx4-qh6g, GHSA-vxq7-64xx-v4gw); no other locked package advisories were returned.

## Validation and rollback
- Runtime: Astral python-build-standalone release `20261013`, `cpython-3.11.17+20261013-aarch64-apple-darwin-install_only.tar.gz`; SHA-256 `d81d757a9785850393cd695a9a686c765a6370fbdc83738589ef2ecd3e5c44b3` matched GitHub release metadata before extraction into ignored `.venv/python-3.11.17/`. Reports Python 3.11.17 and OpenSSL 3.5.9. The system interpreter remains available.
- Package closure: PyPI metadata confirms urllib3 2.8.0 is compatible with requests 2.34.2 (`urllib3>=1.26,<3`); its universal wheel SHA-256 is recorded in audit.lock. All three locks passed `pip_audit --disable-pip --require-hashes`; no known vulnerabilities. Audit and build environments passed `pip check`.
- Focused tests: 20 passed, no skips, exit 0. The first run exposed a test-fixture shebang containing spaces; fixed the fixture without weakening assertions. New coverage checks old/prerelease/other-minor rejection, accepted patched versions, preservation before environment recreation, patch changes and same-version interpreter switches.
- Initial canonical offscreen suite: 494 tests passed in 64.408 seconds, no skips, exit 0. Independent review then identified same-version interpreter cache reuse; added the interpreter-path fingerprint and a regression test. Final canonical suite: **495 tests passed in 83.380 seconds**, no skips, exit 0. The audit, build and final test environments all passed `pip check`.
- macOS app rebuild, ad-hoc signature verification and bundled GUI smoke passed. The bundled `libpython3.11.dylib` contains version 3.11.17. The real default 3.11.2 interpreter was rejected before clearing the existing build environment.
- Compilation, updated documentation file-link checks and diff checks passed. Independent workbook-safety review found no remaining actionable issues after the interpreter identity fix. Workbook production code is unchanged; the full suite covers synthetic transfer, import, history and publication boundaries.
- Rollback: retain the prior interpreter and app separately; revert this branch's implementation commit to restore the previous build policy and audit lock. Reverting the repository cannot remove the ignored isolated interpreter or replace an installed app. No personal input files or Applications copy were touched.
- Plan checkpoint: `a2a27fc`. Final commit and push outcome are reported in the completion message; no PR was requested. All task changes are staged explicitly; isolated runtimes, wheels, test caches and rebuilt app remain ignored local artifacts.

## PR readiness follow-up — October 19, 2026

The user requested a pull request prepared for merge. Integrate current main, preserve its transfer-calibration tests and documentation, publish a ready PR, request Codex review, perform Brooks review, address actionable feedback and validate hosted CI/mergeability. Leave the final merge to the user. Open questions: none.

- [x] Inspect branch/main divergence; main already contains the same urllib3 2.8.0 security fix.
- [x] Resolve the sole merge conflict in this plan by retaining both implementation records below; preserve all non-conflicting transfer tests and guidance.
- [x] Validate the integrated branch and prepare the merge of main into the feature branch: 496 canonical offscreen tests passed in 61.303 seconds, no skips, exit 0; all-lock advisory audit, pip check, compilation, diff check and bundled GUI smoke passed.
- [x] Publish PR #25 and request Codex review. Brooks PR review: 100/100, stable; no actionable findings. Codex feedback and hosted CI remain tracked in the PR and completion report, not as a permanent guarantee in this implementation record.
- [ ] Confirm CI Verify passes and GitHub reports the unmerged PR is mergeable.

## Implementation records retained from main

### Prior documentation plan

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
