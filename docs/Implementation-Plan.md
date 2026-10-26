# Plan

Reduce repeated workbook and archive reads and bound unchanged-ZIP-part memory, preserving the bridge's local operation, reviewed outputs, and source-integrity checks.

## Scope
- In: the efficiency review's three measured priorities (E1 worksheet reuse, E2 refresh verification reuse, E3 ZIP streaming), their deterministic resource regressions (E8), documentation, a reviewed PR into `main`, and the user-approved updates to the dependency locks that block its hosted audit.
- Out: UI threading changes, persistent caches/databases, warm build policy, archive deletion/retention, speculative analysis indexes, unrelated dependency upgrades, and merging the PR. Those recommendations remain conditional on separate workload evidence or product decisions.

## Action items
- [x] Inspect current `main`, relevant architecture/storage/development guidance, and transfer/history/program safety tests; start `codex/local-efficiency` from `f373920` with a clean worktree.
- [x] Checkpoint this resolved plan before implementation; keep disjoint implementation ownership and Git operations coordinated by the parent.
- [x] Reuse operation-scoped coach snapshots and XLSX log/notes row data in `workbook.py`, `importers.py`, and `service.py`; preserve existing helper contracts and ambiguity diagnostics. Add ordinary/marker preview read-count and report/notes parity regressions.
- [x] Keep combined log/notes extraction explicit for transfer previews so log-only history/archive consumers avoid unnecessary note scans; add parity and zero-note-scan regressions from independent review.
- [x] Reuse verified archive entries within one managed refresh in `local_workspace.py` and `managed_history.py`; deduplicate repeated manifest references without a persistent cache or manifest schema changes. Retain source post-parse hashes, selected-coach final hash, workspace fingerprint, relocation/tamper handling and stale worker protections. Add read-count and mutation regressions.
- [x] Stream unchanged ZIP members in `ooxml.py` and `program_template.py`, compare preserved parts in bounded chunks, and retain ZIP metadata/order/comment, namespace preservation, exact uncompressed contents and exclusive publication. Add generated-large-member, late-difference and allocation guards.
- [x] Update `docs/Architecture.md`, `docs/Local-File-Workflow.md`, and `docs/Development.md` with operation scope, unchanged safety gates, and focused resource verification. Record measured results without claiming unmeasured wall-time or monetary savings.
- [x] Run focused preview/import, archive/history, OOXML/program-output and transfer-safety tests; then the complete canonical offscreen suite, compilation and diff checks. Record interpreter and dependency-audit/build limits; use synthetic inputs only.
- [x] Commit each validated coherent slice, inspect the complete branch diff, and push the feature branch with `save-branch`.
- [ ] Update the affected certifi/filelock/setuptools lock entries to audited fixed versions after reviewing dependency constraints and platform wheel hashes; verify closure consistency, the dependency audit, and relevant build-dependency/source checks without weakening the audit gate.
- [ ] Open and attach a PR to `main`, request Codex review, run Brooks review, address actionable feedback and CI failures, and check mergeability until merge-ready or a concrete reported blocker. Leave the PR unmerged.

## Open questions
- None. Operation-scoped reuse is limited to an individual load/preview; hashes at input mutation/publication boundaries remain authoritative.

## Validation and rollback
- Existing safety tests are the behavior contract; add resource guards alongside that contract rather than replacing it with call-count assertions alone.
- Compare ordinary and marker preview proposals/diagnostics; keep malformed/multiple-table handling and changed-input rejection.
- Verify archived bytes after parsing even when enumeration is reused, including mutation during intake and repeated manifest references.
- Bound copy/comparison buffers while continuing full content equality checks; changed worksheet/styles/shared strings may retain their current DOM allocation.
- No data migration or cleanup is introduced. Reverting the implementation commits restores the original read paths without rewriting user files.
- Baseline from the read-only review: 496 tests passed on Python 3.11.2 with Qt 6.11.2. Recheck the current environment; packaged builds require final Python 3.11.17 or a later 3.11 patch.

## Change ledger
- Planning: latest remote `main` matches the reviewed `f373920`; clean detached worktree changed to the requested feature branch. Three measured optimizations plus resource regressions are selected for this PR.
- Worksheet reuse: ordinary and eligible-marker previews now parse the selected coach worksheet once; XLSX sheets feed both logs and compact notes in one pass. Selection's original four-value contract and standalone notes-only import remain supported. Focused preview/integration/calibration/transfer suite: 44 tests passed. Review removed retained row tables from the import result.
- Archive reuse: managed loads share operation-scoped verified entries, and repeated manifest references hash each canonical path once per traversal. Current-link targets are rehashed immediately before link updates; parsed sources, final coach and workspace retain their independent checks. Focused archive/local-workspace/managed-history suite: 40 tests passed, including tamper, symlink-retarget and mutation regressions.
- ZIP streaming: both writers now stream unchanged parts; integrity comparison reads bounded chunks through EOF. Synthetic 16 MiB parts exercise preserved contents/metadata, late differences, length changes and allocation below 8 MiB for workbook/program operations. Focused OOXML/program-output/transfer safety suite: 52 tests passed. The initial shared-shutil test interception was fixed by using a local bounded read/write loop; safety tests were retained unchanged. Combined focused validation: 116 tests passed.
- Integration baseline: canonical offscreen suite passed 512 tests with no skips in 56.529 seconds on Python 3.11.2 / Qt 6.11.2. Independent review then identified unnecessary note scanning for log-only history/archive consumers; make combined extraction opt-in before final validation. No workbook safety defect was found in that observation.
- Review fix: combined XLSX notes extraction now requires `include_notes=True`; only transfer preview opts in. Default history/archive imports skip the note scan and return identical records/diagnostics. The zero-note-scan regression and existing preview/transfer tests passed (45 focused tests). Independent workbook review found no new archive or ZIP safety regression.
- Final local validation after the review fix: canonical offscreen suite reported 513 tests passed in 83.008 seconds with no skips, using pinned Qt 6.11.2 in a temporary environment. Python 3.11.2 was the available local interpreter; no packaged rebuild or native macOS visual check was performed. Compilation and diff checks passed. Hosted CI will audit the unchanged locks and verify Python 3.11.17 before merge readiness is reported.
- Documentation explains operation scope, preserved checks and focused resource tests, with the synthetic before/after measurements in `docs/Development.md`. No dependency, CI, build-policy or user-data changes were needed.
- Publication verification, October 26: canonical suite completed again on the unchanged source with 513 tests passed in 91.018 seconds, no skips, exit status 0; this refreshed the terminal execution evidence after the prior shell session expired. Remote `main` remains `f373920` and is an ancestor of this branch.
- PR #26 is open from `codex/local-efficiency` into `main`, attached to the chat and marked ready for review. Codex review was requested; local Brooks review found no remaining actionable concerns (100/100), with the large diff explicitly sampled around the highest-risk paths. The prior independent note-scan concern was fixed in `1a1c559`.
- Hosted CI run `40402618806` failed before tests in the unchanged dependency audit: certifi 2026.7.22, filelock 3.32.6 and setuptools 84.0.0 have reported advisories. The user was asked whether to expand scope to update the affected locks; no dependency changes are authorized yet. Codex review and passing hosted CI remain readiness gates. No merge conflicts were reported at `69699de`.
- Scope decision, October 26: the user explicitly authorized updating and validating the affected locks. Investigate fixed certifi/filelock/setuptools releases and required constraints, then update the complete affected closures/hashes and re-run audit/CI. Codex completed review of `69699de` with no findings; subsequent changes through `b11b177` only record review/plan status. Request review again after the dependency update.
