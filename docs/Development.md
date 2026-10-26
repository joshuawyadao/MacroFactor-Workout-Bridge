# Development

This guide covers source development and local verification. For project behavior, start with [Architecture](Architecture.md); for commands intended for users, see the [CLI reference](CLI-Reference.md) and [desktop guide](Desktop-Guide.md).

## Prerequisites and source entry points

Source use supports Python 3.11 or newer. The reviewed macOS build requires **final Python 3.11.17 or a later 3.11 patch**, macOS, `zsh`, `iconutil`, and `codesign`. Python 3.11.17 includes standard-library security fixes, including bounded bzip2/LZMA ZIP decompression ([release notes](https://www.python.org/downloads/release/python-31117/)). Python minor-version migrations need a separate review of the wheel closures. A source-only CLI run needs no third-party runtime package; the desktop app and its tests need PySide6. Run commands from the repository root:

```sh
PYTHONPATH=src python3 -m macrofactor_bridge --help
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace --help
```

The package also installs `macrofactor-bridge`, `macrofactor-workspace`, and `macrofactor-bridge-gui` entry points from [pyproject.toml](../pyproject.toml). Keep real inputs in ignored `local-data/` or another private location; use only the synthetic/anonymized files in [tests/fixtures](../tests/fixtures) for public examples.

Select the patched interpreter before running the build and verification commands. For example, if `python3.11` is patched:

```sh
export PYTHON_BIN=python3.11
"$PYTHON_BIN" --version
"$PYTHON_BIN" -c 'import ssl; print(ssl.OPENSSL_VERSION)'
```

Set `PYTHON_BIN` to an absolute interpreter path when needed. Use a maintained distributor for Python 3.11 security releases: python.org no longer supplies 3.11 binary installers. Keep an isolated interpreter under ignored `.venv/` if you want to preserve the system installation. The build preflight rejects unsupported or prerelease interpreters before recreating `.app-build-venv`. CI uses Python 3.11.17. Updating the interpreter does not update an existing app: rebuild and launch the new bundle explicitly.

## Verification

Run the canonical source and offscreen GUI suite from any linked worktree, and follow the process to its unittest summary and exit status. Then complete the [dependency audit](#dependency-locks-and-audit) below:

```sh
./scripts/test.sh
"${PYTHON_BIN:-python3}" -m compileall -q src tests packaging scripts
git diff --check
```

The test runner provisions pinned, hash-verified dependencies on first use. It locates the primary checkout through Git's common directory and shares an ignored `.venv/worktree-tests/` environment keyed by the full Python major.minor.patch version, a fingerprint of the resolved interpreter path, and the SHA-256 of `requirements/test.lock`. A Python patch upgrade or a switch to another interpreter selects a fresh environment rather than reusing the previous runtime. It always launches against the current worktree's `src/`. Internet access is needed on first provision unless the wheels are cached. Set `PYTHON_BIN` to select a supported interpreter or `MACROFACTOR_TEST_VENV_ROOT` to use another environment directory.

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

### Resource regressions

The complete suite includes synthetic checks for preview sheet-read counts, operation-scoped archive verification, and bounded unchanged-ZIP-part allocation. Run their focused subset with the provisioned test interpreter:

```sh
PYTHONPATH=src QT_QPA_PLATFORM=offscreen \
  "$TEST_VENV/bin/python" -m unittest \
  tests.test_preview_efficiency tests.test_archive_efficiency \
  tests.test_zip_streaming tests.test_program_generation -v
```

These checks pair resource assertions with proposals, notes, archive selection, tamper rejection, preserved ZIP contents and program-generation validation. Large ZIP payloads are generated in temporary directories; no personal files or binary fixtures are added. Allocation guards measure traced Python memory, not process RSS or end-to-end latency. Keep wall-clock benchmarks out of the normal gate unless they demonstrate a repeatable workload need; the resource changes introduce no hosted service or runtime dependency.

The October 22, 2026 synthetic comparison against `f373920` observed the following resource changes. These are workload-specific counts/allocations, not predictions of user-visible speed or monetary savings:

| Probe | Before | After |
| --- | --- | --- |
| Selected coach-sheet parses, ordinary / eligible-marker preview | 3 / 5 | 1 / 1 |
| XLSX log sheet reads during preview | 2 | 1 |
| Archive hash calls in one refresh, 1 coach + 64 distinct exports | 261 | 133 |
| Python allocation peak comparing a 32 MiB unrelated ZIP part | 109.43 MiB | 3.19 MiB |

The refresh comparison retains identical dashboard records and independent post-parse/final checks. Memory measurements used Python 3.11.2, a deflated repeated-byte member and `tracemalloc`; the committed tests generate their own payloads and use an allocation ceiling rather than those exact numbers.

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

Check that `python3.11 --version` is 3.11.17 or a later final 3.11 patch; substitute `"$PYTHON_BIN"` on the first line if it selects the reviewed interpreter instead. The audit closure pins `urllib3==2.8.0` to fix HTTPS proxy TLS-policy handling and two chunked-response denial-of-service issues in 2.7.0 ([TLS advisory](https://github.com/urllib3/urllib3/security/advisories/GHSA-8988-9cw3-xx77), [Deflate advisory](https://github.com/urllib3/urllib3/security/advisories/GHSA-gh4c-6fx4-qh6g), [chunk-size advisory](https://github.com/urllib3/urllib3/security/advisories/GHSA-vxq7-64xx-v4gw)). This package belongs to audit tooling, not the offline app runtime.

This reports known package advisories and does not update packages. For a dependency update, resolve the closure on Python 3.11, record reviewed wheel hashes, run `python -m pip check` in the provisioned environment, audit the locks, rebuild the app and run the complete offscreen suite. A lock change must retain exact versions and reviewed wheel hashes; document any separately reviewed source-build requirement before allowing one.

The October 26 audit follow-up updates only affected tooling pins: `certifi==2026.10.23` and `filelock==4.2.4` in the audit closure, and `setuptools==84.1.0` in the app-build closure. Filelock 4 requires Python 3.11, matching the reviewed audit baseline; CacheControl's file-cache dependency accepts it. The reviewed releases provide universal wheels with no new default dependencies. Their hashes were verified against downloaded PyPI artifacts. This clears the reported certifi/filelock advisories and the [setuptools wheel-installation advisory](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w); these packages remain audit/build tooling rather than added application runtime dependencies.

## macOS build and smoke check

```sh
./scripts/build_macos_app.sh
QT_QPA_PLATFORM=offscreen \
  "dist/MacroFactor Workout Bridge.app/Contents/MacOS/MacroFactor Workout Bridge" \
  --smoke-test
```

The build script checks the selected Python runtime, recreates its isolated `.app-build-venv` on every accepted run, installs `app-build.lock`, builds an icon and PyInstaller bundle, ad-hoc signs the `.app`, and verifies that signature. This is a local build, not Developer ID signing or notarization. The smoke command checks the embedded Qt runtime without loading personal history; it does not verify real-data behavior. A source or repository build does not replace an already installed app; launch the new bundle explicitly for manual macOS inspection. Never use a real workout export for automated smoke tests.

## Pull requests and documentation

[CI Verify](../.github/workflows/ci-verify.yml) runs the dependency audit, complete tests, compilation, and diff check for non-draft pull requests and manual dispatches. Draft pull requests do not reserve a runner; marking one ready for review starts verification. New commits cancel superseded runs; merging does not repeat the suite on `main`. Use manual dispatch for a hosted rerun when needed. Record the completed local unittest result and exit status in the PR, plus any native macOS checks relevant to a UI or packaging change.

Keep the [documentation index](README.md) and affected topic page current when changing commands, file formats, user flows, safety checks, or module boundaries. Prefer one canonical explanation with links from overview pages. Use relative Markdown links and concise Mermaid diagrams with a prose equivalent. Examples must be synthetic; no personal workbooks, exports, generated reports, local manifests, credentials, or unredacted local paths belong in documentation or screenshots. See [Contributing](../CONTRIBUTING.md) and the [Security Policy](../SECURITY.md) for broader rules.
