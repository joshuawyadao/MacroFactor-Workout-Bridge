# Plan

Provision the reviewed Python locally with a pinned uv tool, preserving existing environments and exposing an explicit interpreter path for tests, audit and build.

## Scope
- In: checkout-local Python 3.11.17 setup script, failure/reuse tests, development and first-run documentation, reviewed feature PR into main.
- Out: system Python replacement, application dependency upgrades, automatic app installation, merging the PR.

## Action items
- [x] Inspect development/build guides, Python preflight and dependency tests; verify uv's documented installation options.
- [ ] Add a shell setup command using uv 0.13.7 and exact CPython 3.11.17 under ignored `.venv/python`; return only a validated absolute path on stdout.
- [ ] Cover missing/wrong uv, failed downloads, invalid runtime, paths with spaces and repeated setup without external downloads in unit tests.
- [ ] Document uv installation, setup, interpreter selection, audit/build use and retention/rollback in Development; link from README and Getting Started.
- [ ] Run focused tests, canonical suite, dependency audit, compilation and diff checks; attempt real provisioning and record limitations.
- [ ] Review the diff, commit/push, open a PR into main, request Codex review and follow CI/review through completion or a concrete blocker.

## Open questions
- None.
