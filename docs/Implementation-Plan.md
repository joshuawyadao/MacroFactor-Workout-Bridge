# Plan

Split the standalone risk-focused coverage expansion from the local-workspace application work. Preserve the current full commit graph on a dedicated dependent testing branch, remove only coverage commit `770335d` from the existing app branch, retain CI and regression tests coupled to app fixes, and verify both branch outcomes before publishing them.

## Scope
- In: `feat/local-file-workspace`, new `feat/local-file-workspace-test-coverage`, coverage commit `770335d`, its README test description, branch history, PR #5 metadata, validation, commit, and push.
- Out: moving CI infrastructure, moving regression tests committed with app fixes, changing application behavior, merging either branch, or changing the repository default branch.

## Action items
- [x] Preserve the current full branch tip on `feat/local-file-workspace-test-coverage` and publish it before rewriting history.
- [x] Rewrite `feat/local-file-workspace` to omit only `770335d`, replaying all later app, CI, and focused regression commits.
- [x] Resolve replay conflicts by preserving each app fix and its directly associated regression coverage while excluding the standalone coverage additions.
- [x] Verify the app branch contains no standalone coverage-only files or README wording and still passes its complete available suite.
- [x] Commit this split plan on the app branch and update it remotely with `--force-with-lease` after validating the exact target.
- [x] Verify the testing branch still contains the complete standalone coverage expansion and passes all 59 tests.
- [ ] Refresh PR #5's description and check state so it accurately reports the app-only branch after the split.
- [ ] Report both pushed branches, their dependency relationship, commit tips, checks, and any intentionally retained test infrastructure.

## Open questions
- None. “Testing updates” means the standalone coverage expansion introduced by `770335d`; CI and regression tests introduced in the same commits as application fixes remain with the application branch.

## Verification
- The app branch is 665 test/documentation lines smaller across exactly the intended README and six test files; application, package-data, CI, and workflow files are identical to the preserved testing branch.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — all 33 app-branch tests passed; the optional GUI test skipped as expected.
- `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .app-build-venv/bin/python -m unittest discover -s tests -v` — all 33 app-branch tests passed, including GUI coverage.
- On `feat/local-file-workspace-test-coverage`, the standard suite passed all 59 tests with three optional GUI skips and the Qt suite passed all 59 tests.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
