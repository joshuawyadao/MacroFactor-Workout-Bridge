# Getting started

[Documentation index](README.md) · [Project home](../README.md)

This walkthrough builds the macOS app and prepares a private workspace. If you already have the app, start at [prepare your mapping and folders](#prepare-your-mapping-and-folders). For Terminal only, use [CLI setup](#cli-only-setup).

## What you need

| Item | Supported input |
| --- | --- |
| Mac | macOS 13+ on Apple silicon for the local `.app` build |
| Python | 3.11+ for source use; use 3.11 for the reviewed audit/build workflow |
| Exercise log | MacroFactor `.csv` or `.xlsx` export using pounds |
| Coach workbook | `.xlsx` with exercise headers, week labels and existing result cells |
| Program template | Only for Part 2; a separate direct Export Program `.xlsx` |

The log needs `Date`, `Workout`, `Exercise`, `Set Type`, `Reps`, and exactly one supported weight column (`Weight (lb)` or `Weight (lbs)`). Duplicate logical columns are rejected. `RIR` and `Workout Duration` are optional. A program export is not an exercise log. Do not rename kilogram headers to pounds; that would mislabel the values.

A usable export contains at least one completed set with a positive finite rep count. Missing/unsupported rows are reported, and archival success does not guarantee a matching writable coach cell.

## Get the source

If you do not already have a checkout:

```sh
git clone https://github.com/joshuawyadao/MacroFactor-Workout-Bridge.git
cd MacroFactor-Workout-Bridge
python3 --version
```

Run subsequent commands from the directory containing `pyproject.toml`. Keep the checkout and its private workspace in a location you intend to retain.

## Prepare your mapping and folders

Create the personal mapping **once**; `cp -n` keeps an existing copy:

```sh
cp -n config/exercises.example.json config/exercises.local.json
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace setup
```

Open `config/exercises.local.json` in a text editor. Confirm the exercise column and exact names using [Configuration](Configuration.md); the shipped example is synthetic. Keep your private copy out of Git. Set per-side conversions only when you have verified how that exercise's load was exported.

Save inputs without renaming them:

```text
local-data/inbox/coach/          ← coach .xlsx workbooks
local-data/inbox/macrofactor/    ← exercise-log .csv or .xlsx exports
```

For history, include an all-time export when available. A weekly export can transfer that week but cannot reveal workouts absent from all supplied files. Keep program templates outside these inboxes.

## Build and open the app

```sh
./scripts/build_macos_app.sh
```

The script downloads hash-pinned Python/Qt/build dependencies, builds and ad-hoc signs the bundle, and verifies its signature. It recreates `.app-build-venv` each time. Open `dist` in Finder and double-click **MacroFactor Workout Bridge.app**. The built app includes Python and Qt.

The app opens on **Dashboard**. **Data → Auto-load inboxes** normally starts enabled. If it cannot locate your folders, choose **Data → Choose workspace…** and select the `local-data` directory itself. Use **Data → Source status…** to verify selected inputs, coverage and warnings.

You can now [explore the Dashboard or save weekly feedback](Desktop-Guide.md), or select **Update coach workbook** to preview and save completed sets in a new workbook. The full [desktop walkthrough](Desktop-Guide.md#update-a-coach-workbook) explains every transfer step.

If automatic loading is disabled, **Data → Select files manually…** exposes the source selectors. To validate the inboxes yourself:

```sh
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace archive --config config/exercises.local.json
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace status
```

## CLI-only setup

The CLI package has no runtime dependencies. Create an isolated environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/macrofactor-bridge --help
.venv/bin/macrofactor-workspace --help
```

Alternatively, every example can run without installation using `PYTHONPATH=src python3 -m macrofactor_bridge`. You do not need to activate an environment when using its executable by path. See the [command reference](CLI-Reference.md).

## Try a synthetic transfer preview

This reads only the repository's synthetic fixtures and creates no output. It does not need personal files or a local mapping:

```sh
PYTHONPATH=src python3 -m macrofactor_bridge inspect \
  --workbook tests/fixtures/coach-template.xlsx \
  --config config/exercises.example.json
```

Use a worksheet and week printed by `inspect` with `preview`, or omit them to select from the numbered list:

```sh
PYTHONPATH=src python3 -m macrofactor_bridge preview \
  --export tests/fixtures/macrofactor-log.xlsx \
  --workbook tests/fixtures/coach-template.xlsx \
  --config config/exercises.example.json \
  --from-date 2026-08-03 \
  --to-date 2026-08-09
```

The fixtures deliberately include review cases such as ambiguous mappings and occupied cells. Inspect **Proposed writes** and the warnings; this is a demonstration, not a mapping for personal training.

## Keep the installation current

A Git update does not replace an installed app. Follow [Updating the local app](Local-File-Workflow.md#updating-the-local-app-after-a-merge) when you intend to rebuild, and preserve mappings, annotations and source data. Back up the whole workspace separately; archive copies on the same disk do not protect against disk loss.

If a step fails, start with [Troubleshooting](Troubleshooting.md). Developer setup and full validation are in [Development](Development.md).
