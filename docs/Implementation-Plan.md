# Plan

Address the Codex review finding that `current/` selection considers only the current intake run and can roll backward when an older export is uploaded later. Merge verified prior archive history into selection, keep each run's intake entries unchanged, add a rollback regression test, and save the focused fix.

## Scope
- In: verified prior manifest entries, current-link selection across runs, missing/corrupt archive filtering, tests, verification, commit, and push.
- Out: changing archive naming, deleting history, importing workspaces moved from their recorded absolute paths, or changing the kind-specific selection order.

## Action items
- [x] Read structurally valid entries from every prior intake manifest.
- [x] Require each historical archive to exist and match its recorded SHA-256 before selection.
- [x] Combine verified history with new intake entries only for stable-link selection.
- [x] Add a regression test that uploads a newer export, clears it, then uploads an older export later.
- [x] Run focused and full tests plus compile/diff checks.
- [x] Commit and push this Codex feedback fix, then acknowledge the review comment.

## Open questions
- None. Existing kind-specific ordering remains authoritative; this change supplies the complete verified candidate history to that existing decision.

## Verification
- The focused later-but-older upload regression test passed and kept `current/` on the previously archived newer export.
- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .app-build-venv/bin/python -m unittest discover -s tests -v` — all 57 tests passed, including GUI coverage.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
