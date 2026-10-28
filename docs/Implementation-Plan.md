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
- [x] Record local verification, commit and push the completed merge (0d24afc), and request fresh Codex review on the updated PR; review completed clean.
- [x] Watch the new CI Verify run through completion and inspect its msgpack audit failure, addressed below. Leave PR #28 unmerged.

Open questions: none. The user explicitly requested this branch update and CI rerun after merging PR #27.

Local integration validation on 2026-10-28: `./scripts/test.sh` completed with 523 tests passed in 71.061 seconds, no skips, exit 0. Source compilation and both working-tree and staged diff checks passed. Independent integration review found no actionable concerns. All feature application and test files are unchanged from the pre-merge branch; the existing tests validate the inherited dependency integration. Requirements locks and Development.md match merged main exactly. Preserve both PR #27 and PR #28 history records. The two remaining hosted-verification checklist items are tracked live in PR #28 and the completion report after publication, so recording their terminal state does not itself restart checks.

## Approved CI follow-up: msgpack audit dependency

The updated CI run cleared the six previous advisories but stopped before tests at msgpack 1.2.2 (CVE-2026-114613). The user approved the upstream-fixed 1.2.3 patch for audit tooling only.

- [x] Inspect the failed audit log and verify the upstream advisory and 1.2.3 release. Confirm this package is confined to requirements/audit.lock.
- [x] Checkpoint this resolved follow-up plan (5d13143), then change only the msgpack version and its reviewed Python 3.11 macOS/Linux wheel hashes; preserve every other pin/hash and the binary-only policy.
- [x] Verify the selected wheel bytes against PyPI SHA-256 metadata and validate the complete locked audit closure on macOS arm64 and Linux x86-64; run pip check.
- [x] Run all-lock audits with a shared explicit cache twice to exercise the actual CacheControl/msgpack serialization consumer, plus existing dependency regression tests, compilation and diff checks. No new tests are planned for this audit-tool-only patch unless a new application defect appears.
- [x] Update the canonical Development guide and this ledger, save and push the narrow CI fix (e51812f), and request fresh Codex review; review completed clean.
- [x] Inspect hosted readiness: CI was withheld because main advanced through PR #26, requiring the follow-up integration below. The msgpack patch itself changes no application/test/build pins or installed bundles.

Open questions: none. The user explicitly approved the msgpack 1.2.3 patch and wheel/closure verification.

Local patch verification on 2026-10-28: independently downloaded both selected msgpack 1.2.3 wheels from PyPI and matched their bytes to published SHA-256 metadata and the lock. On a checksum-verified isolated Python 3.11.17 runtime, macOS arm64 resolved and installed the complete audit closure with binary-only artifacts and required hashes; `pip check` passed. Linux x86-64 resolved all 29 audit wheels under the same policy. Two all-lock audits using one explicit cache directory both reported no known vulnerabilities; the first populated 37 cache entries. Existing dependency regressions passed (20 tests in 8.204 seconds), compilation and diff checks passed. The canonical 523-test integration run above remains applicable because no application or test logic changed; CI will rerun the full suite after publication. No tests were added for this configuration-only patch.

### Brooks-Lint patch follow-up

**Mode:** PR Review

**Scope:** Approved msgpack patch since 5d13143: canonical dependency guidance and this plan. The lockfile is excluded from decay analysis and separately verified against downloaded artifacts and complete platform closures. Application and test code are unchanged.

**Health Score:** 100/100

**Trend:** Stable at 100.

The patch keeps the audit dependency inside its existing tooling boundary and documents its actual cache consumer.

#### Findings

No actionable concerns. Quick Test Check is inapplicable to this configuration/documentation patch; existing dependency tests and repeated real cached audits provide verification.

#### Summary

- Publish the approved pin and wheel hashes, preserving every other lock entry.
- Track final hosted CI and Codex review in PR #28 and the completion report, so recording terminal hosted status does not itself restart checks. The remaining publication and hosted-verification checklist items above are completed through that live record; leave the PR unmerged.

## Follow-up integration of merged PR #26

Main advanced to 62db9dc while the approved msgpack patch was being verified. PR #26 contains operation-scoped workbook/archive optimizations and the identical msgpack pin/hashes. Integrate that main state so GitHub can run PR #28's checks.

- [x] Inspect the new main commit, affected source/tests/docs and exact audit-lock parity.
- [x] Checkpoint this resolved addition (0ac0655), then merge origin/main without rewriting branch history.
- [x] Preserve the partial-rep confirmation behavior and main's resource/safety improvements in any source overlap; combine canonical documentation and retain all plan/review records.
- [x] Run the canonical offscreen suite, compilation and diff checks, and independently review the integration. Add tests only if conflict resolution introduces behavior not covered by the existing feature and resource regressions.
- [ ] Save and push the completed integration, request Codex review of its final head, then watch CI and review to terminal states. Record hosted status in PR #28 and leave it unmerged.

Open questions: none. Updating PR #28 against current main and resolving conflicts are within the user's requested PR update.

Integration validation: `./scripts/test.sh` passed all 540 tests in 50.455 seconds with no skips and exit 0, including both confirmation and new resource regressions. Compilation and diff checks passed. No new tests were authored for the merge because the combined existing suites cover the resolution. Independent workbook-integrity review found no actionable concerns. The only source conflict was in `service.py`: retain export-bound confirmations and their hashes/report fields while adopting main's single XLSX import with preloaded notes and shared coach-sheet snapshot. All other main source/resource-test files, all dependency locks, and Development.md match 62db9dc exactly. Keep both feature and main implementation/review records.

### Brooks-Lint integration follow-up

**Mode:** PR Review

**Scope:** Incremental conflict resolutions for integration of main 62db9dc: service preview composition, canonical dependency guidance, this plan and review history. Already reviewed resource changes from PR #26 and full/partial feature changes from PR #28 are checked for preservation rather than rescored as new design.

**Health Score:** 100/100

**Trend:** Stable at 100.

The resolved preview composes confirmation handling with operation-scoped reads without new coupling or duplicated parsing.

#### Findings

No actionable findings. Quick Test Check is clean: existing confirmation, preview/resource and mutation/publication tests passed together in the full suite. No test assertions were weakened or removed.

#### Summary

- Publish the merge and request review of its final head; prior clean reviews covered 0d24afc and e51812f.
- Complete hosted CI and final review in the live PR record before reporting readiness. Leave PR #28 unmerged.

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

## Merged efficiency integration record (PR #26)

Historical main record retained for provenance. Its separate merge authorization applied only to PR #26; the current PR #28 remains unmerged.

Integrate the current main branch into PR #26, preserve the reviewed efficiency work and newer security pins, then complete the user-authorized merge and feature-branch cleanup.

### Scope
- In: conflict resolution against main at `37b5b50`, integration validation, the newly reported msgpack audit-tool patch, refreshed PR review/CI, squash merge into main and deletion of `codex/local-efficiency` locally and remotely.
- Out: new application behavior, unrelated dependency upgrades, changes to other branches, private workout data and rebuilding or installing the app.

### Action items
- [x] Inspect live PR #26, merged PR #27, current refs, Development guidance and existing dependency checks; verify a clean feature worktree.
- [x] Checkpoint this resolved plan before merging main into the feature branch.
- [x] Merge main; retain setuptools 84.2.1 and the matching lock hash/security guidance from PR #27, retain both Brooks history records, and keep the efficiency documentation and this current plan.
- [x] Verify all three locks match main exactly, inspect every conflict resolution, and run the canonical 513-test offscreen suite, compilation and diff checks. Existing tests cover this integration; no executable behavior or test files need changing.
- [x] Patch only audit-tool msgpack 1.2.2 to the advisory-fixed release, review macOS arm64/Linux x86-64 CPython 3.11 wheel hashes, install the full hash-pinned audit closure, exercise CacheControl serialization, audit all locks and run existing dependency tests. No application or test edits are needed.
- [ ] Commit and push the integration; refresh Codex review, Brooks review and CI Verify on the final feature head, checking for new comments or changes to main.
- [ ] Squash-merge PR #26 with an expected-head guard, fetch the resulting main commit, verify the efficiency implementation is present, and delete the feature branch locally and remotely.

### Open questions
- None. The user explicitly authorized merging PR #26 and deleting its feature branch. Keep main's newer dependency versions without downgrading them.

### Validation and risk
- Conflicts arise from parallel security-tooling updates and documentation/history edits; preserve both intents without changing production code.
- Main contains the same certifi 2026.10.23 and filelock 4.2.4 updates, plus newer setuptools 84.2.1. Reuse those already reviewed pins and hashes exactly.
- Prior PR #26 validation: 513 local tests passed; CI Verify and final-head Codex review passed at `3fafddb` with no findings. Recheck the integrated head before merging.
- The PR review skill readies the branch; the user's separate merge instruction authorizes the subsequent merge and cleanup.

### Change ledger
- October 28: main advanced through merged PR #27 (`37b5b50`). Read-only merge analysis found overlapping review history, Development guidance, implementation plan and app-build lock changes. Source and test files do not overlap.
- Conflict resolution: retain the current integration plan; keep main's setuptools 84.2.1 lock and canonical security guidance; retain the efficiency resource guidance and both distinct Brooks review records. The historical PR #27 plan remains in Git and its PR body. No application or test changes are introduced.

### Brooks-Lint Review

**Mode:** PR Review

**Scope:** Incremental integration changes since reviewed PR #26 head `3fafddb`: four conflict resolutions in Development guidance, this plan, review history and the app-build lock. All three resulting dependency locks match main `37b5b50` exactly; application source, tests, scripts, packaging and CI remain byte-identical to the reviewed feature head.

**Health Score:** 100/100

**Trend:** Stable at 100.

The integration preserves current security pins and the efficiency implementation without adding coupling or new behavior.

#### Findings

No actionable findings across R1–R6. Generated lock configuration is excluded from code-decay scoring and verified separately for exact equality to current main. The Quick Test Check is inapplicable to this incremental configuration/documentation change; the previously reviewed regression suite remains unchanged and is being rerun.

#### Summary

- Preserve both feature and security review history records and canonical Development guidance.
- Keep final hosted CI, refreshed Codex review and live mergeability as gates before the separately authorized merge and cleanup.
- Integration validation: canonical suite completed with exit 0; test count and timing recorded in the PR before final merge. Compilation and diff checks passed; all three locks exactly match main 37b5b50. No test files changed because no new executable behavior was introduced. The first sandboxed run could not provision PyPI packages; the authorized network-enabled run completed successfully.

### CI follow-up

- Run `40737692224` at `6f52c01` failed in dependency auditing before tests: audit-tool msgpack 1.2.2 is affected by CVE-2026-114613; CI reports 1.2.3 as fixed. This advisory entered the database after the original review. Current main has the same affected pin.
- The user's earlier authorization to update and validate affected locks remains applicable. Limit this follow-up to the msgpack patch and its two existing platform-wheel hashes, keeping main's other pins and source unchanged. Checkpoint this updated plan before changing the lock.
- Refreshed Codex review is running on `6f52c01`; request final-head review after the audit patch. Canonical local integration validation already passed all 513 tests in 61.112 seconds with zero skips and exit 0.

- Audit fix validation: msgpack 1.2.3 requires Python >=3.10 and adds no dependencies. Downloaded CPython 3.11 macOS arm64 and Linux x86-64 wheels matched official PyPI SHA-256 metadata; all other audit pins and both other locks are unchanged. Full hash-enforced audit-closure installation and pip check passed. CacheControl response serialization and FileCache set/get/delete passed. All-lock pip-audit reports no known vulnerabilities; 20 existing dependency tests passed in 7.821 seconds. No application or test files changed; the 513-test integration run remains valid and hosted CI will rerun the suite on the final head.
- Codex review completed on integration commit `6f52c01` with no findings. Request review again after saving this narrow audit patch. Incremental Brooks review of the patch and matching Development guidance found no actionable findings (100/100, stable); generated lock hashes were separately verified and the Quick Test Check remains inapplicable to this configuration/docs delta.
- Final hosted CI/review/merge/cleanup results are tracked in PR #26 to avoid introducing a documentation-only commit after the reviewed final head.
