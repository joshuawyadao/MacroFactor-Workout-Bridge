# Plan

Make the canonical GUI-enabled suite pass when its shared virtual-environment root is overridden for isolated validation. Keep the production runner behavior unchanged and make the default-root test independent of caller environment variables.

## Scope
- In: test environment isolation in `tests/test_build_dependencies.py`, focused and complete GUI-enabled validation, and the implementation record.
- Out: dependency changes, application behavior, runner path semantics, and user-facing documentation changes.

## Action items
[x] Capture the isolated GUI-suite failure and confirm it is limited to the default-root assertion inheriting `MACROFACTOR_TEST_VENV_ROOT`.
[x] Update the default-root test to remove the override from the subprocess environment without weakening its path and fingerprint assertions.
[x] Run the focused build-dependency test module with an outer virtual-environment root override.
[x] Run the complete GUI-enabled suite against the isolated pinned environment.
[x] Run source compilation and diff checks, and confirm the worktree contains only scoped changes.
[x] Save the verified fix on a dedicated branch with this implementation plan.

## Open questions
- None.
