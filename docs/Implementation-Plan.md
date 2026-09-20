# Plan

Close the September 20 regression scan's incomplete GUI validation by following the canonical test runner to a terminal result. Align contributor and PR verification guidance with the runner that includes the optional desktop dependencies, fix any reproduced failures, and prepare a reviewed PR against main.

## Scope
- In: complete offscreen GUI and non-GUI validation, contributor and PR verification guidance, an evidence record, narrow fixes if reproduced, review, commit and push.
- Out: new dashboard features, unrelated refactoring, dependency upgrades, private workout data, installed-app replacement, and merging the PR.

## Action items
[x] Inspect README, CONTRIBUTING.md, the previous implementation ledger, scripts/test.sh, CI Verify, and GUI test coverage; confirm the clean checkout matches main at 7d8a91c.
[x] Create codex/complete-gui-regression-validation for the requested follow-up.
[x] Run ./scripts/test.sh to terminal completion, retaining the final count, skipped-test status, elapsed time and exit status. Investigate any reproducible failure before changing code.
[x] Reproduce the observed accumulation of closed Qt test windows; add shared test-only disposal that stops managed refresh, finishes workers, and processes deferred deletion. Cover cleanup with active jobs and apply it to the existing GUI fixtures without weakening assertions.
[x] Update CONTRIBUTING.md and the PR template to require the canonical runner and terminal evidence; document that partial output is inconclusive and source-only runs may skip GUI coverage.
[x] Record baseline and corrected full-suite results and the remaining boundary of offscreen validation in docs/Regression-Validation.md.
[x] Run compilation, source app-entry smoke verification and diff checks; inspect the completed diff for privacy and accuracy.
[ ] Commit and push the validated changes using save-branch, then open the PR against main and request Codex review.
[ ] Complete Brooks review, terminal CI Verify, Codex feedback handling and fresh mergeability checks; leave the PR unmerged.

## Open questions
- None. The user authorized a feature branch and a PR; any application fix remains contingent on a reproduced failure.

## Review ledger
- Baseline: the prior scan passed 92 focused tests, but did not retain terminal GUI-suite output. Existing historical runs took several minutes; a 30-second tool return alone does not establish a suite timeout.
- Discovery: CI Verify and contributor guidance already use ./scripts/test.sh; the PR template still names the source-only unittest command, which may skip optional GUI tests.
- Independent probe: closing four BridgeWindow instances retained 687, 1,374, 2,061 and 2,748 Qt widgets. Explicit deferred deletion returned the count to zero after each window. Reapplying the global theme to retained widgets makes subsequent tests increasingly expensive; fix the test fixtures, preserving production behavior and assertions.
- Red/green validation: close-only cleanup produced four expected failures in the repeated-window and worker-order regressions. All four lifecycle tests pass with the helper; all 65 focused GUI tests pass in 70.663s with no skips. Optional-Qt-absent discovery skips those 65 tests cleanly.
- Independent patch review found no actionable issue; representative comparison, managed-refresh and timeline-dialog tests each leave zero Qt widgets. Production code, existing assertions and CI timeouts are unchanged.
- Complete canonical validation: all 198 tests pass in 81.669s with no skips and exit status 0. The original baseline also completed: 194 tests passed in 527.235s, no skips, exit status 0. Compilation, source app-entry smoke verification and diff checks pass.
- Brooks PR review of the completed patch: 100/100, no actionable findings; all changed fixtures retain their application assertions and optional-Qt import guards. No production code, dependency or workflow-timeout change is needed.
