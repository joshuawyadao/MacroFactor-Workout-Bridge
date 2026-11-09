# Plan

Provision the reviewed Python locally with a pinned uv tool, preserving existing environments and exposing an explicit interpreter path for tests, audit and build.

## Scope
- In: checkout-local Python 3.11.17 setup script, failure/reuse tests, development and first-run documentation, reviewed feature PR into main.
- Out: system Python replacement, application dependency upgrades, automatic app installation, merging the PR.

## Action items
- [x] Inspect development/build guides, Python preflight and dependency tests; verify uv's documented installation options.
- [x] Add a shell setup command using uv 0.13.7 and exact CPython 3.11.17 under ignored `.venv/python`; return only a validated absolute path on stdout.
- [x] Cover missing/wrong uv, failed downloads, invalid runtime, paths with spaces and repeated setup without external downloads in unit tests.
- [x] Document uv installation, setup, interpreter selection, audit/build use and retention/rollback in Development; link from README and Getting Started.
- [ ] Run focused tests, canonical suite, dependency audit, compilation and diff checks; attempt real provisioning and record limitations.
- [ ] Review the diff, commit/push, open a PR into main, request Codex review and follow CI/review through completion or a concrete blocker.

## Open questions
- None.

## Validation and review ledger
- Eight new setup tests pass; the original 20 dependency/build tests pass. Python compilation, shell syntax and diff checks pass.
- Real uv 0.13.7 provisioned CPython 3.11.17 locally; a second run reused the same interpreter and returned the same path.
- All three dependency locks audited successfully: no known vulnerabilities. Audit environment `pip check` passes.
- Managed-Python macOS build and signature verification pass; the built app's offscreen smoke test passes.
- Read-only scout review identified a missing second-stage runtime validation failure test; added it and verified all eight setup tests pass.
- Canonical offscreen suite in progress. PR creation, hosted checks and Codex review pending.

## Brooks-Lint Review

**Mode:** PR Review
**Scope:** Setup script, setup tests and three documentation changes vs origin/main; no generated files changed.
**Health Score:** 100/100
**Trend:** Stable at 100.

The setup isolates provisioning behind one explicit command with tested error boundaries.

### Findings
No remaining actionable R1–R6 or Quick Test Check findings. Exact tool/interpreter pins are intentional boundary policy; the existing build preflight remains authoritative for build support. Network-independent tests cover failure and reuse, complemented by a real download, reuse, audit and macOS build/smoke check.

### Summary
- Retain explicit interpreter selection and checkout-local storage.
- Hosted CI and Codex review remain pending before merge readiness.
