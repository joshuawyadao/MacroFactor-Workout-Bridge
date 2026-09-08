# Plan

Close Codex's PR feedback by ensuring the macOS application builder never trusts packages left in a previously provisioned virtual environment. Recreate that environment before every hash-locked install and protect the ordering with a focused regression test.

## Scope
- In: macOS build-environment provisioning, its dependency-integrity regression coverage, and the local-build documentation.
- Out: dependency versions or hashes, the shared test environment, application behavior, signing/notarization, and unrelated icon packaging issues.

## Action items
[x] Confirm the unresolved Codex thread is current, actionable, and limited to reuse of `.app-build-venv`.
[x] Recreate `.app-build-venv` unconditionally before installing the reviewed lockfile.
[x] Add a focused test proving environment recreation occurs before the hash-locked dependency install.
[x] Clarify the fresh-environment behavior in the local-build documentation.
[x] Run the focused dependency tests, complete test suite, shell syntax, compilation, and diff checks.
[x] Commit and push the fix, react to the addressed Codex comment, and re-read the PR thread state.

## Open questions
- None.
