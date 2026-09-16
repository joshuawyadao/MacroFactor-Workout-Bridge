# Plan

Make the dashboard open from a remembered local-data workspace, automatically ingest new managed inbox exports, and explain source freshness/coverage without manual file hunting. Consolidate unambiguous workout-day snapshots while retaining provenance, private feedback, and manual overrides.

## Scope
- In: startup workspace discovery, remembered folder, background refresh on managed-file changes, immutable archival of new inbox content, broad-history/newest-export flags, conservative overlap reconciliation, source status/conflict UI, weekly-feedback shortcut, tests/docs, versioned build, commit and push.
- Out: cloud/MacroFactor API access, scanning arbitrary Downloads files, guessed deletions or conflict resolution, changing original workbooks/exports, automatic feedback submission, PR/merge.

## Action items
[x] Inspect history/importer, archive selection, desktop feedback/load flows, existing tests, README and Local-File-Workflow.
[x] Add managed-source discovery and conservative day-snapshot consolidation with content deduplication, validation, source provenance, and explicit conflict/coverage diagnostics.
[x] Archive only new inbox content and reuse verified archives; keep manual weekly-bridge behavior unchanged and reject unsafe managed paths.
[x] Add remembered workspace/autoload controls, background startup/change refresh, source status, manual override, and a latest-logged-week feedback shortcut.
[x] Protect unsaved feedback and stale asynchronous results; cover duplicates, overlapping corrections, newer narrow exports, malformed/changing files, missing roots, and restart idempotence with model/GUI tests.
[x] Update README, Local-File-Workflow and version metadata; run targeted/full tests, source-hash and real-workspace checks, visual QA, packaging/signature/smoke checks.
[x] Commit and push scoped changes using save-branch; keep private snapshots, preferences, inputs, and generated bundles outside Git.

## Open questions
- None. Prefer the broadest observed clean history as baseline (not a claim of complete logging), add new dates and exact multiset supersets, never sum duplicate export snapshots, and flag incompatible same-day sets for review. Newest coach selection uses recorded source modification time and validation, not filename guessing. Background refresh pauses while feedback is unsaved. Only managed folders are scanned; the explicitly supplied September CSV can be copied into its intended inbox without changing the original.

## Verification notes
- `scripts/test.sh`: all 167 tests passed; `git diff --check` passed.
- Added model tests in `tests/test_managed_history.py` and background/UI regression tests in `tests/test_managed_gui.py`, including feedback preservation and post-show scroll layout.
- Real managed-workspace check: seven unique exports, 2,461 completed sets over 115 logged days, January 5–September 11, 2026. One incompatible older day snapshot is flagged rather than merged. Latest valid coach workbook selected automatically.
- Copied only the user-supplied September CSV into the MacroFactor inbox. Hash checks confirmed all original inbox files, the Downloads source, mapping, and saved annotations were unchanged; no weekly feedback was submitted during QA.
- Verified automatic startup, source report, latest-week shortcut, and screenshots at 1120×820 and 900×680. Fixed dynamic scroll sizing after background loads and added a regression test.
- Packaged 0.8.0 (build 11), passed offscreen application smoke test and strict/deep code-signature verification. The installed copy is not replaced by this implementation workflow.
