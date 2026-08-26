# Plan

Address the Codex review finding that an inbox file replaced between hashing and validation can produce a manifest combining metadata for one file with an archive for another. Rehash after validation, reject any mismatch before deduplication or copying, add an atomic-replacement regression test, and save the focused integrity fix.

## Scope
- In: post-validation source integrity, deduplication safety, manifested error behavior, regression coverage, verification, commit, and push.
- Out: file locking, deleting or moving changed inbox files, or retrying automatically while another process is writing.

## Action items
- [x] Rehash each supported source immediately after validation.
- [x] Record a validation error and skip archive/deduplication when the hashes differ.
- [x] Add a regression test that atomically replaces a valid export during validation.
- [x] Run focused and full tests plus compile/diff checks.
- [x] Commit and push this Codex feedback fix, then acknowledge the review comment.

## Open questions
- None. A changed source remains in the inbox and the user can retry after the external writer finishes.

## Verification
- The focused atomic-replacement regression test passed and recorded an error without creating an archive or current link.
- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .app-build-venv/bin/python -m unittest discover -s tests -v` — all 58 tests passed, including GUI coverage.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
