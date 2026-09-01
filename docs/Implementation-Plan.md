# Plan

Standardize the public maintainer name as “Joshua Yadao” across repository licensing, Python package metadata, and macOS application metadata so attribution is consistent. This is a metadata-only cleanup with no executable behavior change.

## Scope
- In: `LICENSE`, `pyproject.toml`, macOS bundle copyright metadata, repository-wide spelling verification, and the implementation plan.
- Out: Commit-author history rewriting, contact-email changes, local Codex checkpoint refs, application behavior, and test fixtures.

## Action items
[x] Replace every non-standard maintainer attribution with “Joshua Yadao”.
[x] Verify licensing, package, and macOS bundle metadata use the standardized spelling.
[x] Confirm no unintended spelling variants remain in the tracked working tree.
[x] Run the complete unit test suite to ensure the metadata-only change does not affect packaging or application behavior.
[x] Compile Python sources and run `git diff --check` as the broader repository verification gate.
[x] Review the final diff, commit the scoped files, and push the feature branch.

## Open questions
- None.
