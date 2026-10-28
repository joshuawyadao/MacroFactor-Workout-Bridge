# Plan

Integrate the current main branch into PR #26, preserve the reviewed efficiency work and newer security pins, then complete the user-authorized merge and feature-branch cleanup.

## Scope
- In: conflict resolution against main at `37b5b50`, integration validation, the newly reported msgpack audit-tool patch, refreshed PR review/CI, squash merge into main and deletion of `codex/local-efficiency` locally and remotely.
- Out: new application behavior, unrelated dependency upgrades, changes to other branches, private workout data and rebuilding or installing the app.

## Action items
- [x] Inspect live PR #26, merged PR #27, current refs, Development guidance and existing dependency checks; verify a clean feature worktree.
- [x] Checkpoint this resolved plan before merging main into the feature branch.
- [x] Merge main; retain setuptools 84.2.1 and the matching lock hash/security guidance from PR #27, retain both Brooks history records, and keep the efficiency documentation and this current plan.
- [x] Verify all three locks match main exactly, inspect every conflict resolution, and run the canonical 513-test offscreen suite, compilation and diff checks. Existing tests cover this integration; no executable behavior or test files need changing.
- [x] Patch only audit-tool msgpack 1.2.2 to the advisory-fixed release, review macOS arm64/Linux x86-64 CPython 3.11 wheel hashes, install the full hash-pinned audit closure, exercise CacheControl serialization, audit all locks and run existing dependency tests. No application or test edits are needed.
- [ ] Commit and push the integration; refresh Codex review, Brooks review and CI Verify on the final feature head, checking for new comments or changes to main.
- [ ] Squash-merge PR #26 with an expected-head guard, fetch the resulting main commit, verify the efficiency implementation is present, and delete the feature branch locally and remotely.

## Open questions
- None. The user explicitly authorized merging PR #26 and deleting its feature branch. Keep main's newer dependency versions without downgrading them.

## Validation and risk
- Conflicts arise from parallel security-tooling updates and documentation/history edits; preserve both intents without changing production code.
- Main contains the same certifi 2026.10.23 and filelock 4.2.4 updates, plus newer setuptools 84.2.1. Reuse those already reviewed pins and hashes exactly.
- Prior PR #26 validation: 513 local tests passed; CI Verify and final-head Codex review passed at `3fafddb` with no findings. Recheck the integrated head before merging.
- The PR review skill readies the branch; the user's separate merge instruction authorizes the subsequent merge and cleanup.

## Change ledger
- October 28: main advanced through merged PR #27 (`37b5b50`). Read-only merge analysis found overlapping review history, Development guidance, implementation plan and app-build lock changes. Source and test files do not overlap.
- Conflict resolution: retain the current integration plan; keep main's setuptools 84.2.1 lock and canonical security guidance; retain the efficiency resource guidance and both distinct Brooks review records. The historical PR #27 plan remains in Git and its PR body. No application or test changes are introduced.

## Brooks-Lint Review

**Mode:** PR Review

**Scope:** Incremental integration changes since reviewed PR #26 head `3fafddb`: four conflict resolutions in Development guidance, this plan, review history and the app-build lock. All three resulting dependency locks match main `37b5b50` exactly; application source, tests, scripts, packaging and CI remain byte-identical to the reviewed feature head.

**Health Score:** 100/100

**Trend:** Stable at 100.

The integration preserves current security pins and the efficiency implementation without adding coupling or new behavior.

### Findings

No actionable findings across R1–R6. Generated lock configuration is excluded from code-decay scoring and verified separately for exact equality to current main. The Quick Test Check is inapplicable to this incremental configuration/documentation change; the previously reviewed regression suite remains unchanged and is being rerun.

### Summary

- Preserve both feature and security review history records and canonical Development guidance.
- Keep final hosted CI, refreshed Codex review and live mergeability as gates before the separately authorized merge and cleanup.
- Integration validation: canonical suite completed with exit 0; test count and timing recorded in the PR before final merge. Compilation and diff checks passed; all three locks exactly match main 37b5b50. No test files changed because no new executable behavior was introduced. The first sandboxed run could not provision PyPI packages; the authorized network-enabled run completed successfully.

## CI follow-up

- Run `40737692224` at `6f52c01` failed in dependency auditing before tests: audit-tool msgpack 1.2.2 is affected by CVE-2026-114613; CI reports 1.2.3 as fixed. This advisory entered the database after the original review. Current main has the same affected pin.
- The user's earlier authorization to update and validate affected locks remains applicable. Limit this follow-up to the msgpack patch and its two existing platform-wheel hashes, keeping main's other pins and source unchanged. Checkpoint this updated plan before changing the lock.
- Refreshed Codex review is running on `6f52c01`; request final-head review after the audit patch. Canonical local integration validation already passed all 513 tests in 61.112 seconds with zero skips and exit 0.

- Audit fix validation: msgpack 1.2.3 requires Python >=3.10 and adds no dependencies. Downloaded CPython 3.11 macOS arm64 and Linux x86-64 wheels matched official PyPI SHA-256 metadata; all other audit pins and both other locks are unchanged. Full hash-enforced audit-closure installation and pip check passed. CacheControl response serialization and FileCache set/get/delete passed. All-lock pip-audit reports no known vulnerabilities; 20 existing dependency tests passed in 7.821 seconds. No application or test files changed; the 513-test integration run remains valid and hosted CI will rerun the suite on the final head.
- Codex review completed on integration commit `6f52c01` with no findings. Request review again after saving this narrow audit patch. Incremental Brooks review of the patch and matching Development guidance found no actionable findings (100/100, stable); generated lock hashes were separately verified and the Quick Test Check remains inapplicable to this configuration/docs delta.
- Final hosted CI/review/merge/cleanup results are tracked in PR #26 to avoid introducing a documentation-only commit after the reviewed final head.
