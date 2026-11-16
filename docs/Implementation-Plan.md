# Plan

Verify the delivered macOS app bundle as well as the Python and Qt source suite.

## Scope
- In: Scoped CI enforcement, automated validation, meaningful orchestration regressions, and canonical verification documentation for MacroFactor Workout Bridge.
- Out: Product feature changes, deployment, paid services or account changes, personal data, physical-device operation, and release signing/publishing.

## Action items
- [ ] Read Development and Local-File-Workflow docs, locked packaging requirements and existing smoke tests.
- [ ] Add a macOS Apple silicon build/signature/offscreen packaged-smoke job using existing locked tools.
- [ ] Keep Ubuntu complete tests and audit, and require both jobs through CI Verify.
- [ ] Add meaningful regression checks for platform selection and aggregate failure handling.
- [ ] Run focused workbook safety, packaging-contract tests and local bundle smoke where dependencies are available.
- [ ] Update verification docs, save and push the isolated branch, and inspect hosted results.

## Discovery notes
- Baseline: `56a9561957f5be2886d1c4790fd5f892128354cb` (`origin/main`), isolated from the original checkout.
- Existing in-progress changes in original project folders remain untouched.
- Missing hosting/account capabilities are reported as concrete limitations; they are not permission to weaken required checks.
