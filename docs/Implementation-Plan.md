# Plan

Address the Codex review finding that an installed `macrofactor-workspace` command cannot find its default exercise mapping outside the source checkout. Bundle the mapping as package data, preserve source and frozen-app behavior, add regression coverage, and verify a built wheel before saving the feedback fix.

## Scope
- In: setuptools package-data configuration, installed-resource lookup, source/frozen compatibility, tests, wheel inspection, commit, and push.
- Out: changing the mapping contents, making `--config` mandatory, or changing mapping selection precedence.

## Action items
- [x] Add the example mapping under the Python package and declare it as setuptools package data.
- [x] Preserve the checkout mapping first, then fall back to the installed package resource.
- [x] Preserve the existing PyInstaller `_MEIPASS/config` lookup.
- [x] Add regression coverage for the installed-resource fallback.
- [x] Build and inspect a wheel, run focused tests, and run diff/compile checks.
- [x] Commit and push this Codex feedback fix, then acknowledge the review comment.

## Open questions
- None. Source checkouts retain their editable root-level mapping while non-editable installs use the identical packaged copy.

## Verification
- `PYTHONPATH=src python3 -m unittest tests.test_desktop_model -v` — all 6 desktop-model tests passed, including the installed-resource fallback.
- A wheel built without isolation contains `macrofactor_bridge/resources/exercises.example.json`.
- The wheel was installed into a clean temporary virtual environment; from `/private/tmp`, `macrofactor-workspace archive` completed without `--config` and wrote a manifest using the packaged mapping.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — all 56 tests passed; three optional Qt tests skipped as expected.
- `python3 -m compileall -q src tests packaging` and `git diff --check` — passed.
