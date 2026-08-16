# MacroFactor Workout Bridge

MacroFactor Workout Bridge is a conservative local Python application that copies completed workout results from a MacroFactor exercise-log export into a selected week of a coach's Excel workbook.

The MVP supports only this direction:

**MacroFactor exercise log → coach `.xlsx` workbook**

It does not create or import MacroFactor programs.

## Safety model

- Preview is read-only and shows every proposed write before an output workbook is created.
- Apply writes to a separate output path. It refuses to use the coach workbook as the output path.
- Apply refuses to overwrite an existing output file.
- Only existing, empty result cells are eligible. Existing values and formulas are always skipped.
- The source workbook and MacroFactor export are hashed before and after apply; a hash mismatch fails the operation.
- The output keeps the same ZIP member list, and every workbook part except the selected worksheet XML must remain byte-identical.
- Updates retain the target cell's style and leave formulas, merged cells, relationships, drawings, and workbook structure intact.
- Exercise matching is exact after case/whitespace normalization and configured aliases. There is no fuzzy matching.
- Missing workouts are never labeled as skipped. Only rows that are present in the export can be reported.
- Zero-rep rows are ignored and reported.
- Real exports, workbooks, generated reports, and outputs are excluded from Git. Only anonymized test fixtures are allowed.

The application never changes the MacroFactor export.

## Requirements

- Python 3.11 or newer
- No runtime Python dependencies
- A MacroFactor exercise-log export in `.csv` or `.xlsx` format
- A coach workbook in `.xlsx` format

## Installation

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

You can then run `macrofactor-bridge`. Without installation, use:

```bash
PYTHONPATH=src python3 -m macrofactor_bridge --help
```

## Configure exercise mappings

Copy the example and edit it locally:

```bash
cp config/exercises.example.json config/exercises.local.json
```

`config/exercises.local.json` should contain one rule per MacroFactor exercise:

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
- `weight_multiplier` defaults to `1`. Set it to `0.5` only for a confirmed per-side exercise.
- `weight_suffix` defaults to an empty string. It is independent of weight conversion.
- `superset_group` and `superset_order` let multiple configured exercises write one target cell with `/` in the configured order.

There is deliberately no general dumbbell, cable, plate-loaded, or machine conversion rule.

## Discover worksheets and weeks

```bash
PYTHONPATH=src python3 -m macrofactor_bridge inspect \
  --workbook "/path/to/Coach_Program.xlsx" \
  --config config/exercises.local.json
```

Worksheet names, week labels, header rows, and result columns are discovered from the workbook. They are not fixed in code. The default configuration recognizes an exercise column headed `Variation` or `Exercise` and week headings matching `Week <number>`. Repeated headers for the same week and result column are consolidated. A merged week header uses its rightmost column as the result column; an unmerged header uses the adjacent column.

## Preview changes

Use an explicit inclusive date range so results cannot be assigned to a coach week accidentally:

```bash
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
- missing or unsupported data.

## Create an output workbook

After reviewing the preview, repeat the selection with `apply` and provide a new output filename:

```bash
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
- Supersets: `50 x 10/60 x 12`
- Drop sets: `100 x 8→70 x 10`
- Bodyweight or a blank MacroFactor weight: `0 x reps`
- Configured per-side conversion plus suffix: `45s x 12`

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The suite uses small anonymized workbooks and verifies parsing, formatting, exact matching, reports, dynamic worksheet/week discovery, empty-cell enforcement, source immutability, style/formula/merge preservation, and byte-identical unrelated workbook parts.

## Known limitations

- Coach workbooks must be `.xlsx`; macro-enabled `.xlsm` files are not supported.
- A target result cell must already exist in the worksheet XML. The application skips a completely absent cell instead of creating one without a trustworthy style.
- One source exercise may appear in only one workout session within the selected date range. Repeated sessions are reported as ambiguous rather than merged.
- Superset exercises must share one configured target and superset group.
- Unsupported duration- or distance-only sets without reps are reported and skipped.
- The application does not calculate formulas or change cached formula results.
- Fuzzy exercise matching and reverse coach-program import are intentionally outside the MVP.
