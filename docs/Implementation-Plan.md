# Plan

Address the Codex review finding that an interrupted new archive copy leaves a poisoned partial file at its canonical destination. Copy into the archive directory under a temporary name, verify its hash, publish it atomically, clean up every failure path, and prove a retry succeeds.

## Scope
- In: new archive copies, legacy-copy fallback, temporary cleanup, hash validation, retry behavior, tests, verification, commit, and push.
- Out: changing canonical names, automatic retries, filesystem durability guarantees beyond atomic rename, or modifying existing corrupt archives.

## Action items
- [x] Copy new archive content into a unique temporary file in the destination directory.
- [x] Verify the temporary copy before atomically replacing it into the canonical path.
- [x] Clean up the temporary file after failures, hash mismatches, races, and success.
- [x] Use the same safe copy path when a legacy hard-link fallback is unavailable.
- [x] Add a regression test that interrupts copying and then succeeds on retry.
- [x] Run focused and full tests plus compile/diff checks.
- [x] Commit and push this Codex feedback fix, then acknowledge the review comment.

## Open questions
- None. Temporary and final paths share a directory/filesystem, preserving atomic rename semantics.

## Verification
- The focused interrupted-copy regression test passed: the failed run left the archive empty and the immediate retry created a valid canonical file.
- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .app-build-venv/bin/python -m unittest discover -s tests -v` — all 59 tests passed, including GUI coverage.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
