# Plan

Address the Codex review finding that syntactically valid but structurally malformed manifest JSON can crash `macrofactor-workspace status`. Validate every decoded container and entry before reading fields, add mixed malformed/legacy regression coverage, and save the focused parser-hardening fix.

## Scope
- In: manifest top-level, timestamp, collection, entry, archive, and validation shapes; regression tests; verification; commit; and push.
- Out: schema migration, rewriting malformed manifests, or changing status selection semantics for valid manifests.

## Action items
- [x] Reject non-object manifest payloads and non-string timestamps.
- [x] Reject non-list legacy entry collections and ignore non-object entries.
- [x] Validate archive and validation field shapes before status selection.
- [x] Prevent embedded entry data from overriding the kind keyed by a `current` mapping.
- [x] Run focused and full tests plus compile/diff checks.
- [x] Commit and push this Codex feedback fix, then acknowledge the review comment.

## Open questions
- None. Malformed manifests are local history artifacts, so status skips them consistently with its existing invalid-JSON behavior.

## Verification
- The focused malformed-manifest/legacy-history regression test passed.
- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .app-build-venv/bin/python -m unittest discover -s tests -v` — all 56 tests passed, including GUI coverage.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
