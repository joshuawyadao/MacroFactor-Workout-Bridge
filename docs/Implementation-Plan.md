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
- Canonical GUI-enabled suite after merging the latest `main`: 68 tests passed.
- `python3 -m compileall -q src tests packaging` passed.
- `git diff --check` passed.
- The rebuilt macOS app is ad-hoc signed, verifies with `codesign --verify --deep --strict`, and reports version 0.3.0 build 4.
- The latest `main` was merged after review fixes, preserving its fresh hash-locked app-build environment hardening.

## Open questions
- None.

## Second Codex review

Finish the three findings from the review of `c136f43`, keeping each fix in its own checkpoint. The README safety model remains the contract: preserve namespace meaning and non-fill formatting, including styles inherited from rows and columns.

- [x] Make desktop review guidance independent of configured marker text; update the existing review-panel assertion.
- [x] Replace global namespace registration during writes with namespace-aware DOM edits that preserve declaration scopes; cover rebound prefixes in both worksheets and stylesheets (15 focused OOXML/integration tests passed).
- [ ] Resolve explicit-cell, row, and column style precedence before cloning a highlight style; cover inherited fonts, borders, alignment, and number formats with synthetic XML.
- [ ] Run focused tests for each checkpoint, then the complete suite, compilation, and diff checks; rebuild and verify the app after the final code change.
- [ ] Push each checkpoint, acknowledge the addressed feedback, and verify the final PR checks and review state.
