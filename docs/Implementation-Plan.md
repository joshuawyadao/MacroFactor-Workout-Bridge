# Plan

Harden the reviewed Python dependency closures without changing package versions. Add cryptographic artifact verification to every locked install and make known-vulnerability auditing a repeatable CI gate over the same exact closures.

## Scope
- In: SHA-256 hashes for both requirements locks, enforced hash checking in build/test installers, a pinned GitHub dependency-audit action, dependency contract tests, and contributor/build documentation.
- Out: dependency-version upgrades, application runtime behavior, Apple signing/notarization, automatic vulnerability remediation, and lockfile regeneration tooling.

## Action items
[x] Collect authoritative PyPI SHA-256 digests for every locked release and add the compatible artifact hashes to both requirements files.
[x] Require pip hash verification in the macOS build and shared test-environment installers.
[x] Add a pinned CI dependency-audit step that checks both complete closures without modifying dependencies.
[x] Extend dependency contract tests to reject unpinned, unhashed, or non-hash-enforced installation paths.
[x] Document the integrity and advisory-audit workflow in the README and contributor guide.
[x] Run focused dependency tests, the complete test suite, compilation, workflow/lock consistency checks, and `git diff --check`.
[x] Commit the completed plan and implementation, then push `codex/dependency-integrity-audit`.

## Open questions
- None.
