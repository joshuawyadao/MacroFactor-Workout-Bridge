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
