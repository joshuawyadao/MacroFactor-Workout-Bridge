# Plan

Finish post-merge synchronization and add a read-only, two-block comparison for one exercise. Reuse the verified history metrics and explicit week layouts, align by relative block week while retaining calendar dates, and keep absent logs and saved context visible.

## Scope
- In: synchronize clean main/primary checkouts to merged PR #15; record its completion; compare weekly sets, training days, top load, and estimated 1RM for one exercise in two blocks; show notes, coverage, and gaps; tests, docs, local app build, commit and push.
- Out: source-file edits, inferred skips/injury/fatigue, automatic date correction, recovery/deload predictions, group-of-block analysis, new export acquisition, and PR creation/merge unless requested.

## Action items
[x] Verify clean checkouts and synchronize them to merged main without changing private data; create `codex/block-comparison` from main.
[x] Add a pure comparison model using existing history summaries; preserve explicit ordering, unequal lengths, missing metrics, and export-range coverage; reject ambiguous/undated/non-Monday blocks.
[x] Add a comparison panel with exercise/two-block selectors, shared-scale trend chart, paired weekly rows, calendar dates, and saved block/week context; reset stale results and preserve selections on reload.
[x] Test alignment, shared chart scales, absent logs, partial/out-of-range weeks, ambiguous dates, exact exercise selection, context, and immutable inputs using synthetic data; cover desktop selection/reload/error behavior.
[x] Update README and Local-File-Workflow with comparison semantics, limitations, and refresh steps; preserve the prior PR completion record below.
[x] Run focused and full tests, compilation, diff checks, real-data read-only GUI verification, visual inspection, and a signed app build/smoke test.
[x] Commit and push only scoped code/tests/docs with save-branch; leave the working tree clean and report the feature branch.

## Prior milestone completion
- PR #15 merged into main as `7e3bf5b` after CI Verify passed and all three addressed review threads were resolved with user approval.
- The old feature branch was deleted locally and remotely. Version 0.4.1 and verified private week layouts were installed with recoverable backups; source workbook and export remained unchanged.

## Open questions
- None. Use confirmed Monday–Sunday block dates and the existing export. Missing logs remain unknown; explicit skip information can remain in saved notes, but workbook Skip review markers are not treated as confirmations. A newer all-time export can be selected later.

## Verification notes
- Source, config, and annotation hashes stayed unchanged during real-input GUI comparison checks.
- Visual inspection found the source controls crowding out comparison rows; successful loads now collapse those controls behind Show sources, and long block notes scroll inside a bounded read-only field.
- Actual Qt rendering caught a collision with QWidget's metric method; renamed the chart field and selector and retained a render regression test.
- Long real-world week notes initially expanded rows enough to obscure the comparison. Rows now stay compact and expose the complete context in tooltips; a long-note regression guards this behavior.
- All 113 tests pass, including 11 new comparison/model and desktop regressions. Compilation, diff checks, real-input source hash checks, normal/minimum-window visual checks, and the 0.5.0 bundle signature/smoke test pass. The previous 0.4.1 bundle is retained as a private local backup.
- No workbook, export, private annotation, generated app, or screenshot is included in the feature branch. PR creation and merge remain separate follow-up actions.
