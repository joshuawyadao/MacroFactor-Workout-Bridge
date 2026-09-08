# Plan

Address every actionable Codex review thread on PR #10 while preserving the conservative workbook workflow. Protect namespace-qualified OOXML extensions, reject duplicate logical export headers, propagate malformed XLSX-row diagnostics into empty-day marker eligibility, align configurable marker messaging, correct the README safety guarantees, and advance the macOS build number. Re-run focused and complete verification, then save and push the review fixes.

## Scope
- In: all six Codex review findings, focused regression tests for each behavior, implementation-plan traceability, full tests, compilation, diff checks, commit, and push.
- Out: reverse program import, fuzzy exercise matching, live MacroFactor integration, personal configuration or files, merging PR #10, and unrelated refactoring.

## Action items
[x] Preserve original namespace prefixes and markup-compatibility declarations when edited worksheet and stylesheet XML are reserialized.
[x] Reject CSV and XLSX exercise-log tables that contain duplicate headers after alias canonicalization.
[x] Report non-empty XLSX workout rows without a date and withhold empty-day markers when those rows make absence uncertain.
[x] Describe configurable marker colors generically in review text while keeping the bundled default yellow.
[x] Correct the README's highlighted-marker safety guarantees and increment the macOS bundle build number.
[x] Add focused regression tests for each review fix.
[x] Run the focused tests, complete suite, source compilation, diff checks, and rebuilt-app signature and metadata validation.
[x] Prepare the completed review fixes for commit and push; resolve the GitHub review threads after the new commit is published.

## Verification
- Focused integration and desktop-model suite: 19 tests passed.
- Canonical GUI-enabled suite: 65 tests passed.
- `python3 -m compileall -q src tests packaging` passed.
- `git diff --check` passed.
- The rebuilt macOS app is ad-hoc signed, verifies with `codesign --verify --deep --strict`, and reports version 0.3.0 build 4.

## Open questions
- None.
