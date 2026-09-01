# MacroFactor Workout Bridge

[![CI Verify](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/actions/workflows/ci-verify.yml/badge.svg)](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/actions/workflows/ci-verify.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![macOS 13+](https://img.shields.io/badge/macOS-13%2B-000000?logo=apple)](https://www.apple.com/macos/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

MacroFactor Workout Bridge is a conservative local macOS application that copies completed workout results from a MacroFactor exercise-log export into a selected week of a coach's Excel workbook. It includes a double-clickable graphical app and an optional command-line interface.

The supported direction is intentionally narrow:

**MacroFactor exercise log → coach `.xlsx` workbook**

It does not create or import MacroFactor programs.

> **Project status:** Source-first personal utility. It processes files locally, has no hosted backend, and does not distribute a signed or notarized binary.

## Engineering highlights

- **Preview before write:** every proposed workbook change is shown before an output can be created.
- **Immutable inputs:** source hashes are checked around apply, and output must use a distinct path that does not already exist.
- **Surgical OOXML edits:** only the selected worksheet XML may change; unrelated workbook parts must remain byte-identical.
- **Conservative matching:** exercise names use exact normalized aliases, with no fuzzy or inferred matches.
- **Reviewable ambiguity:** duplicates, occupied cells, zero-rep rows, unsupported data, and unmatched exercises are reported instead of guessed.
- **Local-first privacy:** the app and CLI do not upload workout or workbook data and have no runtime network dependency.
- **Reproducible verification:** anonymized fixtures cover parsing, formatting, workbook integrity, desktop behavior, and packaged-app smoke behavior.

## Architecture

```mermaid
flowchart LR
    Export["MacroFactor export"] --> Importer["Strict export importer"]
    Mapping["Local exact-alias config"] --> Service["Preview/apply service"]
    Coach["Coach .xlsx workbook"] --> OOXML["OOXML workbook reader/writer"]
    Importer --> Service
    OOXML --> Service
    Service --> Preview["Human-reviewable preview"]
    Preview -->|explicit apply| Output["New workbook copy"]
```

```text
src/macrofactor_bridge/  Import, matching, formatting, OOXML, service, CLI, and desktop workflow
packaging/               PyInstaller entry point, specification, and icon generation
scripts/                 Reproducible local macOS application build
config/                  Synthetic example exercise mapping
tests/                   Unit, integration, GUI, and anonymized workbook fixtures
```

## Privacy and security

- Real MacroFactor exports, coach workbooks, generated reports, application outputs, local mappings, and local workspaces are excluded from Git.
- Only deliberately anonymized fixtures under `tests/fixtures/` may be committed.
- The application processes selected files on the local machine and does not transmit their contents.
- The build script downloads declared Python build dependencies, but the built application has no runtime network integration.
- The local `.app` is ad-hoc signed. It is not Developer ID signed, Apple-notarized, or suitable for trusted direct-download distribution.

See the [Security Policy](SECURITY.md) to report a vulnerability privately. Never attach real workout or workbook data, credentials, or unredacted local paths to a public issue.

## Safety model

- Preview is read-only and shows every proposed write before an output workbook is created.
- Apply writes to a separate output path and refuses to use the coach workbook as the output path.
- Apply refuses to overwrite an existing output file.
- Only existing, empty result cells are eligible. Existing values and formulas are always skipped.
- The source workbook and MacroFactor export are hashed before and after apply; a hash mismatch fails the operation.
- The output keeps the same ZIP member list, and every workbook part except the selected worksheet XML must remain byte-identical.
- Updates retain the target cell's style and leave formulas, merged cells, relationships, drawings, and workbook structure intact.
- Exercise matching is exact after case and whitespace normalization plus configured aliases. There is no fuzzy matching.
- Missing workouts are never labeled as skipped. Only rows present in the export can be reported.
- Zero-rep rows are ignored and reported.

The application never changes the MacroFactor export.

## Private local file workspace

For recurring use, keep personal inputs and generated files under the Git-ignored `local-data/` directory instead of Downloads:

```bash
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace setup
```

Drop coach workbooks into `local-data/inbox/coach/` and MacroFactor exercise-log exports into `local-data/inbox/macrofactor/`, then validate and archive them. Keep their downloaded names; no manual renaming is needed:

```bash
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace archive \
  --config config/exercises.local.json
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace status
```

Every validated copy starts with its UTC upload/intake date for easy searching. MacroFactor names also include their workout-date range, and all archive names include a content hash. Stable files under `local-data/current/` always point to the versions to select in the app. Every run creates a JSON manifest, identical content is deduplicated, and inbox files are never moved, deleted, renamed, or changed. Save app outputs under `local-data/generated/`. See [Local File Workflow](docs/Local-File-Workflow.md) for the directory layout, naming examples, weekly routine, privacy rules, and recovery limitations.

Exports must contain at least one usable completed set. Malformed history entries are skipped, and moving the whole workspace preserves archive selection and status paths. Custom `--root` locations receive local Git ignore rules for all managed data directories, including private manifests and reports; existing tracked files are not automatically untracked.

## Use the macOS app

After a local build, the application is at:

```text
dist/MacroFactor Workout Bridge.app
```

Open Finder, navigate to `dist`, and double-click **MacroFactor Workout Bridge**. The app is self-contained; using the built app does not require Python or Terminal.

The app guides one workflow:

1. Choose the MacroFactor `.csv` or `.xlsx` exercise-log export.
2. Choose the coach `.xlsx` workbook.
3. Use the bundled exercise mapping, or save an editable JSON copy and select it.
4. Click **Discover**, then select the worksheet and coach week.
5. Confirm the inclusive workout dates. **Use latest export week** selects Monday through Sunday around the export's latest workout row; it does not infer that an absent workout was skipped.
6. Click **Preview workbook changes** and inspect the proposed-change table and **Review needed** panel.
7. Click **Create safe workbook copy…** and choose a new `.xlsx` filename.
8. Optionally save the full review and validation report as JSON.

The bundled mapping is an example, not a promise that every personal exercise name is configured. Use **Save editable copy…** to create a normal JSON file outside the repository, add exact aliases and confirmed conversions, then preview again. The app never edits the mapping stored inside its bundle.

### Requirements

- macOS 13 or newer on Apple silicon
- Python 3.11 or newer to build from source
- A MacroFactor exercise-log export in `.csv` or `.xlsx` format
- A coach workbook in `.xlsx` format

### Build locally

The first build requires internet access so the isolated environment can install the reviewed PySide6 and PyInstaller dependency closure:

```sh
./scripts/build_macos_app.sh
```

The script creates `dist/MacroFactor Workout Bridge.app`, embeds Python and Qt, generates the app icon, applies an ad-hoc signature, and verifies the bundle. Build environments and application artifacts are excluded from Git.

The app-build dependency closure is pinned in `requirements/app-build.lock`; the direct optional dependencies in `pyproject.toml` use the same PySide6 and PyInstaller versions. Update this lockfile only as a tested unit: resolve it on Python 3.11, run `python -m pip check`, rebuild the app, and run the offscreen GUI suite. The command-line package deliberately has no runtime dependencies.

Because the app is built locally, it should open normally on that Mac. A copied or downloaded build is not Apple-notarized; macOS may require Control-clicking the app, choosing **Open**, and confirming **Open**. Developer ID signing and notarization are outside the current project.

## Optional command-line workflow

Create a virtual environment and install the project:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Run `macrofactor-bridge`, or use the source tree without installation:

```sh
PYTHONPATH=src python3 -m macrofactor_bridge --help
```

### Configure exercise mappings

Copy the synthetic example and edit the ignored local file:

```sh
cp config/exercises.example.json config/exercises.local.json
```

Each mapping rule follows this shape:

```json
{
  "canonical": "Dumbbell Walking Lunge",
  "source_aliases": ["Dumbbell Walking Lunge"],
  "coach_aliases": ["Walking Lunge"],
  "weight_multiplier": 0.5,
  "weight_suffix": "s"
}
```

- `source_aliases` are exact names accepted from the MacroFactor export.
- `coach_aliases` are exact names accepted in the workbook's exercise column.
- `coach_context_aliases` optionally disambiguate repeated exercise-column labels by requiring an exact match in another text cell on the same row. For example, `Abs` can be paired with the exact variation `hanging leg raises (3ct tempo eccentric)` without selecting a separate GHD sit-up row.
- `weight_multiplier` defaults to `1`. Set it to `0.5` only for a confirmed per-side exercise.
- `weight_suffix` defaults to an empty string and is independent of weight conversion.
- `superset_group` and `superset_order` let multiple configured exercises write one target cell with `/` in configured order.

There is deliberately no general dumbbell, cable, plate-loaded, or machine conversion rule.

### Discover worksheets and weeks

```sh
PYTHONPATH=src python3 -m macrofactor_bridge inspect \
  --workbook "/path/to/Coach_Program.xlsx" \
  --config config/exercises.local.json
```

Worksheet names, week labels, header rows, and result columns are discovered from the workbook rather than fixed in code. The default configuration recognizes an exercise column headed `Variation` or `Exercise` and week headings matching `Week <number>`. Repeated headers for the same week and result column are consolidated. A merged week header uses its rightmost column as the result column; an unmerged header uses the adjacent column.

### Preview changes

Use an explicit inclusive date range so results cannot be assigned to a coach week accidentally:

```sh
PYTHONPATH=src python3 -m macrofactor_bridge preview \
  --export "/path/to/MacroFactor-Exercise_Log.xlsx" \
  --workbook "/path/to/Coach_Program.xlsx" \
  --config config/exercises.local.json \
  --sheet "Training Block" \
  --week "Week 1" \
  --from-date 2026-08-03 \
  --to-date 2026-08-09 \
  --report reports/week-1-preview.json
```

Omit `--sheet` or `--week` to choose from an interactive numbered list.

Preview reports:

- proposed cell values;
- unmatched source exercises;
- configured aliases matching multiple workbook rows;
- exercises appearing in multiple workout sessions in the selected date range;
- zero-rep and missing-rep rows;
- occupied result cells;
- missing or unsupported data;
- relevant exercise-level notes found in MacroFactor's `Active Program` table. Notes are review-only and are not appended to result cells.

### Create an output workbook

After reviewing the preview, repeat the selection with `apply` and provide a new output filename:

```sh
PYTHONPATH=src python3 -m macrofactor_bridge apply \
  --export "/path/to/MacroFactor-Exercise_Log.xlsx" \
  --workbook "/path/to/Coach_Program.xlsx" \
  --config config/exercises.local.json \
  --sheet "Training Block" \
  --week "Week 1" \
  --from-date 2026-08-03 \
  --to-date 2026-08-09 \
  --output outputs/Coach_Program-week-1.xlsx \
  --report reports/week-1-apply.json
```

Apply refuses to create an output when there are no proposed writes.

## Result formatting

- Completed sets: `weight x reps`
- Repeated weight: `200 x 8, 7`
- Weight changes: `200 x 8, 7; 180 x 10`
- Myo and mini sets: `160 x 10+3+2`
- Supersets: `50/60 x 10/12, 9/11`
- Superset weight changes: `50/60 x 10/12; 50/55 x 9/11`
- Drop sets: `100 x 8→70 x 10`
- Bodyweight or blank MacroFactor weight: `0 x reps`
- Configured per-side conversion plus suffix: `45s x 12`

## Verification

Run the complete source and graphical suite:

```sh
./scripts/test.sh
python3 -m compileall -q src tests packaging
git diff --check
```

The first test run creates an environment under the primary project checkout's already-ignored `.venv/worktree-tests/` directory and requires internet access unless the pinned wheels are already cached. Its directory name contains the Python version and SHA-256 fingerprint of `requirements/test.lock`: worktrees with the same test dependencies reuse one environment, while branches with different locks cannot modify an environment used by another test run. Linked Git worktrees discover the shared root through Git's common directory, and the runner always prepends the launching worktree's `src/` directory to `PYTHONPATH`.

Use `MACROFACTOR_TEST_VENV_ROOT=/absolute/path` to override the directory containing fingerprinted environments. Existing files directly inside `.venv` remain available to the primary checkout; the runner manages only its `worktree-tests/` child. To run only tests that do not require the optional graphical dependency, bypass the runner:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

After building the application, verify its embedded Qt runtime:

```sh
QT_QPA_PLATFORM=offscreen \
  "dist/MacroFactor Workout Bridge.app/Contents/MacOS/MacroFactor Workout Bridge" \
  --smoke-test
```

GitHub-hosted CI runs the complete Python and offscreen desktop test suite for non-draft pull requests and manual dispatches. Draft pull requests do not reserve a runner; marking one ready for review starts verification. A newer update to the same pull request cancels superseded work, and merging does not repeat the same suite on `main`. Use the Actions tab's manual **CI Verify** dispatch when a hosted rerun is needed.

The suite uses small anonymized workbooks and verifies parsing, formatting, exact matching, reports, desktop defaults and controls, dynamic worksheet/week discovery, empty-cell enforcement, source immutability, style/formula/merge preservation, and byte-identical unrelated workbook parts. Direct source-only runs skip the GUI test when PySide6 is unavailable; the canonical runner provisions it and executes the test.

## Known limitations

- Coach workbooks must be `.xlsx`; macro-enabled `.xlsm` files are not supported.
- A target result cell must already exist in the worksheet XML. The application skips a completely absent cell instead of creating one without a trustworthy style.
- One source exercise may appear in only one workout session within the selected date range. Repeated sessions are reported as ambiguous rather than merged.
- Superset exercises must share one configured target and superset group, contain the same number of completed standard sets, and are paired by set position in configured exercise order.
- Current MacroFactor `.xlsx` exports expose exercise-level notes in `Active Program`, but the `Workout Log` table does not expose program-level or session-level notes. Exercise notes appear in review output only and represent the current active-program value rather than a historical note attached to one completed set.
- Unsupported duration- or distance-only sets without reps are reported and skipped.
- The application does not calculate formulas or change cached formula results.
- The `.app` build targets Apple silicon and is locally signed but not Apple-notarized.
- Fuzzy exercise matching and reverse coach-program import are intentionally outside the current scope.

## Contributing

Issues and pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md) before participating. Report conduct concerns through the private channel in the [Code of Conduct](CODE_OF_CONDUCT.md#enforcement). Follow the [Security Policy](SECURITY.md#reporting-a-vulnerability) for vulnerabilities: never publish exploit or sensitive details, but if private vulnerability reporting is unavailable, a sanitized public issue may request a private contact channel.

## License

Released under the [MIT License](LICENSE). MacroFactor is a product of Stronger By Science Technologies LLC; this independent project is not affiliated with or endorsed by MacroFactor.
