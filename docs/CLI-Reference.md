# Command-line reference

[Documentation index](README.md) · [Project home](../README.md)

Run commands from the repository root. Install the CLI with the [getting-started instructions](Getting-Started.md#cli-only-setup), or use the source directly:

```sh
PYTHONPATH=src python3 -m macrofactor_bridge --help
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace --help
```

After installation, `.venv/bin/macrofactor-bridge` and `.venv/bin/macrofactor-workspace` are equivalent entry points. Add `--help` after any subcommand for its full flags.

## Command map

| Command | Required inputs | File effects |
| --- | --- | --- |
| `inspect` | `--workbook`, `--config` | Prints coach worksheets/weeks. |
| `preview` | Above plus `--export`, `--from-date`, `--to-date` | Prints proposed transfers; optional new `--report` JSON. |
| `apply` | Preview inputs plus new `--output` | Builds a fresh preview and writes a new coach workbook, then prints the result; optional report. No interactive approval prompt. |
| `program-inspect` | `--workbook`, `--config` | Prints coach blocks and safe plan weeks. |
| `program-preview` | Same; `--template` needed for generation readiness | Prints prescriptions/blockers; optional report. |
| `program-generate` | Same plus `--template`, new `--output` | Creates a candidate only after validation; optional report. |
| `program-batch` | `--workbook`, `--config`, `--template`, new `--output-dir` | Writes private batch reports; candidates only with `--generate`. |

Part 1 uses optional `--sheet` / `--week` selections; omitted selections prompt when needed. Program commands also use `--block` and repeatable `--week`; base mode can derive all weeks or an explicitly configured headerless duration. Use explicit selections in scripts.

## Weekly workbook transfer

Create and review [your mapping](Configuration.md) first. Paths and dates below are examples; substitute the selected inputs and real inclusive workout dates. Run `preview` and review its warnings before repeating the selection with `apply`. The CLI does not load a saved preview JSON as authorization.

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
- yellow empty-day `Skip` markers that require confirmation before the workbook is shared.

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

Apply refuses to create an output when there are no proposed writes. When some cells are eligible, apply can write them while reporting other unmatched, ambiguous or skipped items; inspect the entire preview before sharing a partial result.

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

Per-side load conversions are explicit mapping rules; repetitions remain as exported. No general machine or dumbbell conversion is inferred. See [Configuration](Configuration.md).

## Private workspace commands

```sh
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace setup
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace archive --config config/exercises.local.json
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace status
```

Create the mapping before `archive`. The global `--root /path/to/workout-data` goes **before** `setup`, `archive` or `status`. Setup creates directories/ignore rules, archive validates and copies inputs and updates current links, and status reads the selected history. See [Local File Workflow](Local-File-Workflow.md) for naming and recovery.

## Reports and exit status

Report paths must be new and distinct from inputs, configuration and generated workbooks. Existing files and symlink aliases are refused. Reports can include private source paths, raw coach text and exercise details; store them under ignored `local-data/generated/reports/` or `reports/`.

| Command group | Exit status |
| --- | --- |
| Main CLI | `0` when the command completes, `2` on handled input/configuration/workbook errors or invalid arguments. |
| `program-preview` | Can return `0` with blocking findings: inspect **Generation safe** and the report's `generation_safe`; successful preview is not permission to generate. |
| `program-batch` | `0` for all selected items ready/generated/explicitly skipped; `1` for partial or input-invalidated runs; `2` for fatal setup errors. |
| Workspace | `0` on success; `2` for errors, including archive runs with rejected inputs (valid inputs may still be archived). |

For Part 2 commands and exact policy examples, continue to [Program generation](Program-Generation.md) or [Batch review](Program-Batch.md). For safeguards and fallback publication limits, see [output/report safety](Local-File-Workflow.md#preview-output-and-report-safety).
