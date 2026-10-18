# Plan

Update the reviewed macOS build runtime from Python 3.11.2 to the patched Python 3.11.17 baseline, then audit the exact locked packages before selecting any package changes. Keep the Python minor version and hash-verified dependency closures coherent, rebuild the app, and validate synthetic workbook and desktop behavior.

## Scope
- In: Python build-runtime selection and preflight, CI runtime pin, dependency advisory checks and any confirmed fixes, dependency/build regression tests, README and canonical setup/development guidance, local app rebuild, commit checkpoints and branch push.
- Out: Python minor-version migration, unrelated package freshness updates, global interpreter replacement, personal workbooks/exports, app installation into Applications, pull requests and merging.

## Action items
[x] Inspect README, docs/Development.md, docs/Getting-Started.md, manifests, all three locks, build/test scripts, CI and tests/test_build_dependencies.py; verify Python 3.11.17 upstream security release and an Apple-silicon runtime source.
[x] Resolve the detached-checkout save branch: the user selected codex/patched-python-runtime; checkpoint this plan before implementation.
[ ] Provision an isolated, checksum-verified Python 3.11.17 runtime for this checkout, leaving the system interpreter available for rollback.
[ ] Audit all exact locked dependencies; update only packages with confirmed security/reliability fixes and preserve closure/hash consistency.
[ ] Require patched Python 3.11 for macOS packaging before environment recreation; pin CI to the reviewed patch and update relevant setup/development docs.
[ ] Extend build-dependency tests for rejected old/prerelease/wrong-minor interpreters, accepted patched versions, and failure before build-environment mutation.
[ ] Run focused tests, full offscreen tests, all-lock advisory audit, pip check, compilation, macOS build/signature and bundled-runtime smoke checks using the patched interpreter; use only synthetic data.
[ ] Integrate the independent workbook-safety review, record validation and rollback details, commit the completed implementation and push the selected branch.

## Open questions
- None. The user approved codex/patched-python-runtime. PyPI advisory data confirms urllib3 2.7.0 in audit.lock needs the 2.8.0 security fixes (GHSA-8988-9cw3-xx77, GHSA-gh4c-6fx4-qh6g, GHSA-vxq7-64xx-v4gw); no other locked package advisories were returned.
