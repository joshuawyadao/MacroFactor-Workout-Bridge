# Plan

Verify the delivered macOS app bundle as well as the Python and Qt source suite.

## Scope
- In: Scoped CI enforcement, automated validation, meaningful orchestration regressions, and canonical verification documentation for MacroFactor Workout Bridge.
- Out: Product feature changes, deployment, paid services or account changes, personal data, physical-device operation, and release signing/publishing.

## Action items
- [ ] Read Development and Local-File-Workflow docs, locked packaging requirements and existing smoke tests.
- [x] Add a macOS Apple silicon build/signature/offscreen packaged-smoke job using existing locked tools.
- [x] Keep Ubuntu complete tests and audit, and require both jobs through CI Verify.
- [x] Add meaningful regression checks for platform selection and aggregate failure handling.
- [x] Replace unavailable macOS ARM `setup-python` 3.11.17 distribution with pinned, checksum-verified uv and the existing exact-version local provisioner; retain ARM and patched-floor checks.
- [x] Use an inline official-release uv download after the repository's GitHub-owned Actions policy rejected the third-party setup action before job startup.
- [x] Accept the verified release's parenthesized provenance in the existing uv version guard; retain strict rejection of other versions and malformed suffixes.
- [ ] Run focused workbook safety, packaging-contract tests and local bundle smoke where dependencies are available.
- [ ] Update verification docs, save and push the isolated branch, and inspect hosted results.

## Discovery notes
- Baseline: `56a9561957f5be2886d1c4790fd5f892128354cb` (`origin/main`), isolated from the original checkout.
- Existing in-progress changes in original project folders remain untouched.
- Missing hosting/account capabilities are reported as concrete limitations; they are not permission to weaken required checks.
- Focused build-dependency and CI contract tests passed locally. The full suite could not provision the pinned Qt wheel under restricted network access; the local Python 3.11.2 is below the packaged-build preflight minimum of 3.11.17. Hosted verification remains pending.
