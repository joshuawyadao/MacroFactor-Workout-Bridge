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
[ ] Document module ownership, build/test/dependency maintenance and documentation conventions; update CONTRIBUTING and label historical validation evidence.
[ ] Verify links/anchors, SVG rendering, command help and synthetic CLI examples; run canonical tests, compilation, dependency audit and diff checks. No test changes are planned because executable behavior is unchanged.
[ ] Review input/output/privacy claims and advanced-policy coverage; commit each coherent documentation slice with validation evidence.
[ ] Push the feature branch, open a PR, run Brooks and Codex review, and follow CI/mergeability through a terminal result without merging.

## Open questions
- None. Use source-controlled SVG and Mermaid diagrams with text equivalents, keep private screenshots and exports out of the documentation, and organize around users’ tasks.

## Validation and checkpoints
- User guides: synthetic fixture inspect/preview produced six expected writes with deliberate review cases; all local links/anchors and nine JSON examples parsed successfully. The workflow SVG was rendered and visually checked for clipping and readable contrast.
- Setup commands use non-overwriting `cp -n`; the private mapping is created before archive commands. CLI apply and program-preview exit semantics are explicit.
- Program and workbook-safety documentation audits are ongoing; contributor documentation is complete and awaits the next checkpoint review.
