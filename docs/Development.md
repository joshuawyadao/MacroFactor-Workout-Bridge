# Development

This guide covers source development and local verification. For project behavior, start with [Architecture](Architecture.md); for commands intended for users, see the [CLI reference](CLI-Reference.md) and [desktop guide](Desktop-Guide.md).

## Prerequisites and source entry points

Use Python 3.11 or newer. The macOS app build requires macOS, `zsh`, `iconutil`, and `codesign`. A source-only CLI run needs no third-party runtime package; the desktop app and its tests need PySide6. Run commands from the repository root:

```sh
PYTHONPATH=src python3 -m macrofactor_bridge --help
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace --help
```

The package also installs `macrofactor-bridge`, `macrofactor-workspace`, and `macrofactor-bridge-gui` entry points from [pyproject.toml](../pyproject.toml). Keep real inputs in ignored `local-data/` or another private location; use only the synthetic/anonymized files in [tests/fixtures](../tests/fixtures) for public examples.

## Verification

Run the canonical source and offscreen GUI suite from any linked worktree, and follow the process to its unittest summary and exit status. Then complete the [dependency audit](#dependency-locks-and-audit) below:

```sh
./scripts/test.sh
python3 -m compileall -q src tests packaging
git diff --check
```

The test runner provisions pinned, hash-verified dependencies on first use. It locates the primary checkout through Git's common directory and shares an ignored `.venv/worktree-tests/` environment keyed by Python version and the SHA-256 of `requirements/test.lock`. It always launches against the current worktree's `src/`. Internet access is needed on first provision unless the wheels are cached. Set `PYTHON_BIN` to select a supported interpreter or `MACROFACTOR_TEST_VENV_ROOT` to use another environment directory.

For a focused test, first run the canonical suite once to provision the environment, then locate its interpreter without running tests again:

```sh
TEST_VENV="$(./scripts/test.sh --print-venv)"
PYTHONPATH=src QT_QPA_PLATFORM=offscreen \
  "$TEST_VENV/bin/python" -m unittest tests.test_transfer_safety -v
```

After provisioning, the same environment can launch the source GUI (omit `--help` to open it):

```sh
PYTHONPATH=src "$TEST_VENV/bin/python" -m macrofactor_bridge.desktop --help
```

Replace the test module with one relevant to your change. A direct `PYTHONPATH=src python3 -m unittest discover -s tests -v` run can skip GUI modules when PySide6 is absent; it does not prove desktop coverage. GUI fixtures should call `self.addCleanup(dispose_widget, widget)` immediately after creating a top-level widget, within the existing optional-Qt import guard. Register temporary-directory cleanup first so widget workers finish before fixture files disappear. See [the historical GUI validation note](Regression-Validation.md) for the original cleanup defect and its dated results; use the commands above for the current gate.

## Dependency locks and audit

Three reviewed, exact-version lock files have separate roles: [test.lock](../requirements/test.lock) provisions the canonical test runner; [app-build.lock](../requirements/app-build.lock) provisions the PyInstaller build; [audit.lock](../requirements/audit.lock) provisions `pip-audit` itself. They pin complete dependency closures with wheel SHA-256 hashes and binary-only installation. [Dependency tests](../tests/test_build_dependencies.py) check consistency between the locks, `pyproject.toml` optional dependencies, packaging and CI. When changing dependencies, update the affected closures and keep those parity checks passing.

CI audits all three closures. To reproduce its dependency check locally, use Python 3.11; the reviewed audit wheel hashes target that interpreter on Linux x86-64 and Apple-silicon macOS:

```sh
python3.11 -m venv --clear .venv/audit
.venv/audit/bin/python -m pip install \
  --only-binary=:all: --require-hashes \
  --requirement requirements/audit.lock
.venv/audit/bin/python -m pip_audit \
  --disable-pip --require-hashes \
  --requirement requirements/audit.lock \
  --requirement requirements/app-build.lock \
  --requirement requirements/test.lock
```

This reports known package advisories and does not update packages. For a dependency update, resolve the closure on Python 3.11, record reviewed wheel hashes, run `python -m pip check` in the provisioned environment, audit the locks, rebuild the app and run the complete offscreen suite. A lock change must retain exact versions and reviewed wheel hashes; document any separately reviewed source-build requirement before allowing one.

## macOS build and smoke check

```sh
./scripts/build_macos_app.sh
QT_QPA_PLATFORM=offscreen \
  "dist/MacroFactor Workout Bridge.app/Contents/MacOS/MacroFactor Workout Bridge" \
  --smoke-test
```

The build script recreates its isolated `.app-build-venv` on every run, installs `app-build.lock`, builds an icon and PyInstaller bundle, ad-hoc signs the `.app`, and verifies that signature. This is a local build, not Developer ID signing or notarization. The smoke command checks the embedded Qt runtime without loading personal history; it does not verify real-data behavior. A source or repository build does not replace an already installed app; launch the new bundle explicitly for manual macOS inspection. Never use a real workout export for automated smoke tests.

## Pull requests and documentation

[CI Verify](../.github/workflows/ci-verify.yml) runs the dependency audit, complete tests, compilation, and diff check for non-draft pull requests and manual dispatches. Draft pull requests do not reserve a runner; marking one ready for review starts verification. New commits cancel superseded runs; merging does not repeat the suite on `main`. Use manual dispatch for a hosted rerun when needed. Record the completed local unittest result and exit status in the PR, plus any native macOS checks relevant to a UI or packaging change.

Keep the [documentation index](README.md) and affected topic page current when changing commands, file formats, user flows, safety checks, or module boundaries. Prefer one canonical explanation with links from overview pages. Use relative Markdown links and concise Mermaid diagrams with a prose equivalent. Examples must be synthetic; no personal workbooks, exports, generated reports, local manifests, credentials, or unredacted local paths belong in documentation or screenshots. See [Contributing](../CONTRIBUTING.md) and the [Security Policy](../SECURITY.md) for broader rules.
