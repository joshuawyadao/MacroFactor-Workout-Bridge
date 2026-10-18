# Plan

Update the reviewed macOS build runtime from Python 3.11.2 to the patched Python 3.11.17 baseline, then audit the exact locked packages before selecting any package changes. Keep the Python minor version and hash-verified dependency closures coherent, rebuild the app, and validate synthetic workbook and desktop behavior.

## Scope
- In: Python build-runtime selection and preflight, CI runtime pin, dependency advisory checks and any confirmed fixes, dependency/build regression tests, README and canonical setup/development guidance, local app rebuild, commit checkpoints and branch push.
- Out: Python minor-version migration, unrelated package freshness updates, global interpreter replacement, personal workbooks/exports, app installation into Applications, pull requests and merging.

## Action items
[x] Inspect README, docs/Development.md, docs/Getting-Started.md, manifests, all three locks, build/test scripts, CI and tests/test_build_dependencies.py; verify Python 3.11.17 upstream security release and an Apple-silicon runtime source.
[x] Resolve the detached-checkout save branch: the user selected codex/patched-python-runtime; checkpoint this plan before implementation.
[x] Provision an isolated, checksum-verified Python 3.11.17 runtime for this checkout, leaving the system interpreter available for rollback.
[x] Audit all exact locked dependencies; update only packages with confirmed security/reliability fixes and preserve closure/hash consistency.
[x] Require patched Python 3.11 for macOS packaging before environment recreation; pin CI to the reviewed patch, separate test environments by patch and interpreter identity, and update setup/development docs.
[x] Extend build-dependency tests for rejected old/prerelease/wrong-minor interpreters, accepted patched versions, and failure before build-environment mutation.
[x] Run focused tests, full offscreen tests, all-lock advisory audit, pip check, compilation, macOS build/signature and bundled-runtime smoke checks using the patched interpreter; use only synthetic data.
[x] Integrate the independent workbook-safety review, record validation and rollback details, and prepare the validated implementation for final commit and push on the selected branch.

## Open questions
- None. The user approved codex/patched-python-runtime. PyPI advisory data confirms urllib3 2.7.0 in audit.lock needs the 2.8.0 security fixes (GHSA-8988-9cw3-xx77, GHSA-gh4c-6fx4-qh6g, GHSA-vxq7-64xx-v4gw); no other locked package advisories were returned.

## Validation and rollback
- Runtime: Astral python-build-standalone release `20261013`, `cpython-3.11.17+20261013-aarch64-apple-darwin-install_only.tar.gz`; SHA-256 `d81d757a9785850393cd695a9a686c765a6370fbdc83738589ef2ecd3e5c44b3` matched GitHub release metadata before extraction into ignored `.venv/python-3.11.17/`. Reports Python 3.11.17 and OpenSSL 3.5.9. The system interpreter remains available.
- Package closure: PyPI metadata confirms urllib3 2.8.0 is compatible with requests 2.34.2 (`urllib3>=1.26,<3`); its universal wheel SHA-256 is recorded in audit.lock. All three locks passed `pip_audit --disable-pip --require-hashes`; no known vulnerabilities. Audit and build environments passed `pip check`.
- Focused tests: 20 passed, no skips, exit 0. The first run exposed a test-fixture shebang containing spaces; fixed the fixture without weakening assertions. New coverage checks old/prerelease/other-minor rejection, accepted patched versions, preservation before environment recreation, patch changes and same-version interpreter switches.
- Initial canonical offscreen suite: 494 tests passed in 64.408 seconds, no skips, exit 0. Independent review then identified same-version interpreter cache reuse; added the interpreter-path fingerprint and a regression test. Final canonical suite: **495 tests passed in 83.380 seconds**, no skips, exit 0. The audit, build and final test environments all passed `pip check`.
- macOS app rebuild, ad-hoc signature verification and bundled GUI smoke passed. The bundled `libpython3.11.dylib` contains version 3.11.17. The real default 3.11.2 interpreter was rejected before clearing the existing build environment.
- Compilation, updated documentation file-link checks and diff checks passed. Independent workbook-safety review found no remaining actionable issues after the interpreter identity fix. Workbook production code is unchanged; the full suite covers synthetic transfer, import, history and publication boundaries.
- Rollback: retain the prior interpreter and app separately; revert this branch's implementation commit to restore the previous build policy and audit lock. Reverting the repository cannot remove the ignored isolated interpreter or replace an installed app. No personal input files or Applications copy were touched.
- Plan checkpoint: `a2a27fc`. Final commit and push outcome are reported in the completion message; no PR was requested. All task changes are staged explicitly; isolated runtimes, wheels, test caches and rebuilt app remain ignored local artifacts.
