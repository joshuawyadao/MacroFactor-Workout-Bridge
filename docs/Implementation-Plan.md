# Plan

Close the shared test runner's concurrency-coverage gap by exercising two real runner processes against one fresh temporary environment root through the existing `PYTHON_BIN` seam. Preserve the runner's public interface and behavior, then publish a reviewed, green pull request for user approval without merging it.

## Scope
- In: deterministic concurrent-provisioning coverage, plan traceability, targeted and complete verification, branch save, pull-request creation, CI, and review follow-up.
- Out: application behavior, dependency-version changes, new runner configuration, maintainer-name changes, merging the pull request, and updating the second feature branch before this branch merges.

## Action items
[x] Add a lightweight fake Python adapter in `tests/test_build_dependencies.py` that exercises the runner without network access or a real virtual environment.
[x] Launch two `scripts/test.sh` processes against one fresh temporary root and verify both succeed, provisioning runs once, the environment becomes ready, and the lock is released.
[x] Run the focused dependency tests, the complete GUI-enabled suite, compilation, dependency, and diff checks.
[x] Confirm `README.md` and `CONTRIBUTING.md` remain accurate; avoid documentation changes if observable runner behavior is unchanged.
[ ] Commit and push the scoped follow-up on `codex/shared-test-environment`.
[ ] Open a ready-for-review PR, request Codex review, run Brooks review, and shepherd all visible checks to a terminal state without merging.

## Open questions
- None.
