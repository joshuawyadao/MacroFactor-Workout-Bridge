# Plan

Display confirmed full and partial rep counts separately in coach-workbook imports while preserving MacroFactor's original numeric reps for history and source verification.

## Scope
- In: explicit per-set full/partial counts, coach-result formatting, transfer preview and CLI input, private confirmation persistence, regression tests, and affected user documentation.
- Follow-up in: integrate the merged PR #27 dependency fixes from main, preserve both documentation/review records, and rerun local and hosted verification for PR #28.
- Out: guessing counts from decimal reps, changing source exports or existing generated workbooks, changing history calculations, automatic equipment conversions, and installing or replacing the packaged app.

## Action items
- [x] Inspect Architecture.md, CLI-Reference.md, Local-File-Workflow.md, Desktop-Guide.md, Development.md, importer/model/formatter paths, and existing integration, numeric, and desktop tests.
- [x] Verify the supplied export's schema and official MacroFactor full/partial logging and data-export documentation. The supplied Workout Log has only a combined Reps column; separate counts cannot be uniquely recovered.
- [x] Resolve the confirmation workflow and detached-branch questions below, then checkpoint this plan on the selected branch. The user approved the preview editor and codex/separate-full-partial-reps branch, including commit and push.
- [x] Add a narrowly scoped full/partial confirmation contract keyed to the export hash and original set identity, retaining raw Reps for history and refusing stale or invalid confirmations.
- [x] Integrate confirmed counts with coach-result formatting, including repeated loads, converted weights, special sets, and paired supersets. Preserve legacy integer-only formatting and make unresolved fractional sets visible for review.
- [x] Expose set confirmation in the desktop transfer preview and a corresponding explicit CLI input, saving confirmation data only in private workspace storage without modifying exports.
- [x] Add synthetic regression tests for import/preview/apply, full-only and partial-only counts, ambiguous decimals, malformed or stale confirmations, unchanged numeric history, special-set formatting, and desktop review behavior.
- [x] Update CLI-Reference.md, Desktop-Guide.md, Local-File-Workflow.md, Configuration.md, and Architecture.md to describe the supported data, confirmation step, display, and preservation boundaries.
- [x] Run targeted formatter/integration/numeric/desktop tests, the complete offscreen suite via scripts/test.sh, compilation, and git diff --check; review the final diff and privacy boundaries.
- [x] Record validation and checkpoint commits and prepare the completed branch for the final save-branch commit and push; the final chat report records publication.

## Open questions
- None. Use an explicit per-set preview editor and remember confirmations for the same export. Create and save codex/separate-full-partial-reps. Preserve original numeric history and exports.

## Validation and save record

- Plan checkpoint: b259656. Core, CLI and transfer regression checkpoint: f1c39e8.
- Final canonical `./scripts/test.sh`: 523 tests passed, zero skips, exit 0. Focused core/transfer/numeric/safety suite: 57 tests passed. Focused Qt editor/desktop/model suite: 19 tests passed.
- Source compilation and `git diff --check` passed. Synthetic offscreen preview/editor rendering verified the new controls and displayed state. Private workout files were not used as automated fixtures or included in commits.
- Independent workbook-integrity review found one editor validation issue: invalid Save closed the dialog and discarded edits. Validation now runs inside the editor; real button-click coverage verifies values survive invalid Save. Re-review found no remaining actionable issues.
- Confirmations remain private and tied to export bytes and original set identity; raw history calculations, exports and existing workbooks are unchanged. Save checks preserve unrelated-date confirmations and detect observed external changes, without promising filesystem-wide locking.
- The installed app bundle is intentionally unchanged. Rebuild it from the completed branch to use the feature in a packaged application; source execution already includes the editor. No dependency or packaging changes were required.

## PR review cycle

- PR #28: Display confirmed full and partial reps in workbook imports; branch codex/separate-full-partial-reps.
- Brooks PR review on 2026-10-26: 100/100, stable against the preceding PR Review record; no actionable findings. Sampled the 18-file diff across all production confirmation, transfer and UI paths plus corresponding tests. The large diff is cohesive and includes substantial test/documentation coverage. No generated files were excluded.
- Codex review was requested; hosted review and CI readiness are checked after this record is saved. No review-driven source changes or additional tests were required by the Brooks pass.
- GitHub reports the branch mergeable without conflicts. Leave the PR unmerged; the final chat report records the latest Codex and CI states.

## Follow-up plan: integrate merged PR #27 (2026-10-28)

Update PR #28 from current main after the user merged PR #27, retaining the full/partial rep feature and the reviewed dependency fixes.

- [x] Confirm PR #27 is merged, PR #28 remains open, and the working tree is clean; inspect Development.md, both implementation records, and changed dependency locks.
- [x] Checkpoint this resolved plan (6ef6a26), then merge origin/main into codex/separate-full-partial-reps without rewriting branch history.
- [x] Resolve overlapping implementation-plan and Brooks-history edits by preserving both feature and dependency-review evidence; retain main's exact reviewed pins and hashes.
- [x] Run the canonical offscreen suite, source compilation, and diff checks. Existing regressions cover this integration; add tests only if a new defect requires a behavioral fix.
- [ ] Record local verification, commit and push the completed merge, and request fresh Codex review on the updated PR.
- [ ] Watch the new CI Verify run through completion, inspect any observed failure, and confirm fresh review and mergeability state. Leave PR #28 unmerged.

Open questions: none. The user explicitly requested this branch update and CI rerun after merging PR #27.

Local integration validation on 2026-10-28: `./scripts/test.sh` completed with 523 tests passed in 71.061 seconds, no skips, exit 0. Source compilation and both working-tree and staged diff checks passed. Independent integration review found no actionable concerns. All feature application and test files are unchanged from the pre-merge branch; the existing tests validate the inherited dependency integration. Requirements locks and Development.md match merged main exactly. Preserve both PR #27 and PR #28 history records. The two remaining hosted-verification checklist items are tracked live in PR #28 and the completion report after publication, so recording their terminal state does not itself restart checks.

## Merged dependency refresh record (PR #27)

Historical implementation and validation evidence retained from main; the current PR #28 integration checklist is above.

Refresh only the vulnerable audit and build dependencies, verify their complete hash-pinned closures on Python 3.11, and prepare a reviewed pull request with a rebuilt, smoke-tested macOS app.

### Scope
- In: `certifi` 2026.7.22 → 2026.10.23 and `filelock` 3.32.6 → 4.2.4 in `requirements/audit.lock`; `setuptools` 84.0.0 → 84.2.1 in `requirements/app-build.lock`; canonical dependency notes in `docs/Development.md`; local and hosted verification; PR review ledger.
- Out: PySide6, Shiboken, PyInstaller, Python minor-version migrations, application behavior, personal data, system Python, installed Applications bundles, and merging the PR.

### Action items
- [x] Inspect the README, Development guide, all three locks, `pyproject.toml`, build/test scripts, CI and `tests/test_build_dependencies.py`; refresh `origin/main` and current advisory evidence.
- [x] Commit this resolved plan on `codex/dependency-security-refresh` before implementation (`fbbb735`).
- [x] Verify target wheel SHA-256 values against PyPI and refresh only the affected exact pins/hashes, keeping the rest of each complete closure fixed.
- [x] Validate the filelock major upgrade against CacheControl's actual file-cache API and Python 3.11 requirements; use an isolated audit environment, dependency resolution, `pip check`, and repeated cached audits. Existing dependency tests and real consumer checks cover this configuration-only change, so no new test files are planned.
- [x] Update `docs/Development.md` with the security rationale and the audit-only filelock compatibility boundary; retain binary-only and required-hash installation instructions.
- [x] Resolve/install audit and app-build closures on patched Python 3.11.17, validate Linux x86-64 audit wheels, audit all three locks, and run the existing focused dependency tests plus the full offscreen GUI suite, compilation and diff checks.
- [x] Rebuild the macOS app, verify the ad-hoc signature, run its embedded-runtime smoke check, and confirm the bundled Python version. Each lock closure is an independent rollback boundary; do not roll back to vulnerable versions for routine continued use.
- [x] Save and push the implementation branch, open a PR against `main`, request Codex review and run Brooks review; record concrete validation below and track live review/CI completion in the PR before handing off for merge.

### Open questions
- None. Current PyPI metadata confirms the three targets are available and have no reported advisories. All three current vulnerable versions are reported by PyPI; leaving filelock unchanged would fail the existing all-lock CI audit. CacheControl requires `filelock>=3.8.0` with no major upper bound; the upgrade remains confined to audit tooling and must pass its real cache path before acceptance.

### Validation results

- Audited all 37 unique exact locked packages against current PyPI advisory data; only certifi, filelock and setuptools required changes. Target universal-wheel SHA-256 values matched PyPI; pip accepted the complete unchanged remainder of each closure with required hashes.
- Provisioned an isolated Python 3.11.17 / OpenSSL 3.5.9 runtime from the checksum-verified python-build-standalone 20261013 archive; the system interpreter and installed app were not modified.
- Audit environment: full dependency resolution and `pip check` passed. CacheControl 0.14.4 with filelock 4.2.4 passed cache miss/read/write/replace/delete, separate-body cache, 40 concurrent distinct-key writes and 40 same-key writes. All-lock `pip_audit --disable-pip --require-hashes` passed twice with the same explicit cache directory, reporting no known vulnerabilities each time.
- Linux x86-64 Python 3.11 audit closure downloaded successfully with binary-only wheels and required hashes.
- Existing dependency/documentation tests: 20 passed in 8.831 seconds, exit 0. No test files changed because application behavior and desktop dependencies are unchanged; real cache-consumer and build checks exercise the updated third-party integration.
- macOS app rebuilt and ad-hoc signature verification passed; embedded GUI smoke passed. Bundled `libpython3.11.dylib` reports Python 3.11.17. Build environment `pip check` passed with setuptools 84.2.1. Compilation and `git diff --check` passed.
- Complete offscreen suite: 496 tests passed in 62.765 seconds, no skips, exit 0. Final hosted CI and Codex review status are tracked in [PR #27](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/pull/27) and the completion report rather than recorded as a permanent guarantee here.

### PR review ledger

- Plan checkpoint: `fbbb735`; isolated audit-tool upgrade checkpoint: `782edae`. Build tooling and canonical dependency notes are saved separately so the two lock updates remain independently reviewable.
- Independent workbook-integrity review: no actionable findings; application source, test files, desktop pins, packaging scripts and CI are unchanged. Remaining gates are hosted CI and PR reviews.
- The old GitHub CI/comment helper skill paths referenced by the PR workflow are not installed. Use native GitHub CLI/API check diagnostics and thread-aware GraphQL reads if needed; this does not change the review or verification gates.
- Opened PR #27 after saving the implementation in `020d487`; requested Codex review. Brooks review and independent safety review both found no actionable concerns. Hosted CI and the final Codex review must complete before declaring merge readiness; no review feedback, CI failure or conflict has required an implementation change at this checkpoint.

### Brooks-Lint Review

**Mode:** PR Review

**Scope:** PR #27 changes versus `origin/main` (`f373920`): `docs/Development.md` and this plan; two dependency lockfiles excluded from decay analysis as generated configuration and separately checked for advisories, hashes and closure compatibility. Review metadata contains no production logic.

**Health Score:** 100/100

**Trend:** Stable at 100.

The dependency refresh preserves the existing environment boundaries without adding application coupling or new abstractions.

#### Findings

No actionable findings. The existing lock policy deliberately pins complete closures, and matching security notes are appropriate canonical documentation. Quick Test Check is inapplicable because this PR changes only configuration and documentation; existing tests, direct cache checks and the rebuilt app provide verification.

#### Summary

- Retain the three advisory-backed package updates and reviewed wheel hashes.
- Complete Codex review, hosted CI and a fresh mergeability check before handing off PR #27; leave the merge to the maintainer.
