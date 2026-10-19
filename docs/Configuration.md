# Exercise mapping and configuration

[Documentation index](README.md) · [Project home](../README.md)

The app matches **exact names after Unicode, case and whitespace normalization**. It does not guess that similar names, equipment or movements are equivalent. Start with the synthetic [example](../config/exercises.example.json), then confirm every personal mapping in Preview.

## Create your private configuration

Copy the synthetic example without overwriting an existing mapping, then edit the ignored local file:

```sh
cp -n config/exercises.example.json config/exercises.local.json
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

The workbook section can optionally enable an empty-day review marker:

```json
{
  "empty_day_marker": {
    "text": "Skip",
    "fill_color": "FFFF00"
  }
}
```

The marker is proposed only when the selected dates contain usable workout data, the programmed day has no matched result, the target cell is empty, and no unmatched, ambiguous, zero-rep, or otherwise unusable rows make the absence uncertain. The yellow fill is preserved in the generated workbook while the cell's existing font, border, alignment, and number format remain intact.

- `source_aliases` are exact names accepted from the MacroFactor export.
- `coach_aliases` are exact names accepted in the workbook's exercise column.
- `coach_context_aliases` optionally disambiguate repeated exercise-column labels by requiring an exact match in another text cell on the same row. For example, `Abs` can be paired with the exact variation `hanging leg raises (3ct tempo eccentric)` without selecting a separate GHD sit-up row.
- `weight_multiplier` defaults to `1`. Set it to `0.5` only for a confirmed per-side exercise.
- `weight_suffix` defaults to an empty string and is independent of weight conversion.
- `superset_group` and `superset_order` let multiple configured exercises write one target cell with `/` in configured order. Part 1 requires the same number of completed standard sets for each movement, paired by set position; unsupported mixed/special-set combinations remain unresolved.

There is deliberately no general dumbbell, cable, plate-loaded, or machine conversion rule. A load conversion does not double or halve exported repetitions, and the transfer does not add machine base weight.

Per-side weight and per-side repetitions are independent. For an exercise confirmed to export combined weight, use `weight_multiplier: 0.5` and `weight_suffix: "s"` to display the load per side. Equal repetitions on each side do not mean doubling or halving the logged count. A different exercise on similar equipment still needs its own confirmed rule.

Part 1 aliases must match the configured workbook exercise column. If that column is `Style`, map its labels and use `coach_context_aliases` for exact variation disambiguation when needed. A Part 2 configuration using variation descriptions is not automatically a Part 1 transfer mapping. Register a performed substitution by its exact export name without changing the intended future program.

Machine names requested for a particular week remain manual annotations, not permanent result prefixes. Existing annotated result cells remain protected as occupied.

## Workbook discovery settings

These keys live in the top-level `workbook` object, alongside the top-level `exercises` list. A rule fragment is one item in that list, not a complete configuration file.

| Key | Default / example | Purpose |
| --- | --- | --- |
| `exercise_header_labels` | `["Variation", "Exercise"]` | Exact header labels used to find exercise rows. Use `["Style"]` only after confirming your workbook uses that column for transfer identity. |
| `week_header_pattern` | See the example's regular expression | Recognizes numbered week headers; verify the resulting columns with `inspect`. |
| `empty_day_marker` | Enabled as yellow `Skip` in the example; absent by default | Optional review prompt when a programmed day has no matched session and no uncertainty prevents it. |

Week labels, header rows and target result columns are discovered from the workbook. A merged week header uses its rightmost column as the result column; an unmerged header uses its adjacent column. Repeated headers for the same week/result column are consolidated. A target result cell must already exist and be empty.

Keep the full top-level JSON object when editing; JSON does not allow comments or trailing commas. `weight_multiplier` must be finite and positive. Use [CLI inspect and preview](CLI-Reference.md#weekly-workbook-transfer) to verify the resulting configuration before writing a workbook. The app's **Save editable copy…** creates a copy of its bundled mapping; the bundled file itself is never edited.

## History annotations are separate

Block dates, week context and optional `week_layout` live in the private annotation file, normally `local-data/annotations/workout-history.json`. They do not belong in the exercise mapping. Prefer the app's **Training notes** editor for dates and feedback. Advanced layouts are documented in [Local File Workflow](Local-File-Workflow.md#irregular-coach-week-layouts).

## Part 2 settings

Part 2 reuses exact exercise identities but adds policy choices. Keep a separate ignored `config/program.local.json`, and use block-specific profiles for reviewed corrections. See the [program guide](Program-Generation.md) for prerequisites, source guards and complete examples; use the [batch guide](Program-Batch.md) for a manifest containing complete scoped configurations.

| Setting under `program` | Default | Opt-in behavior / requirement |
| --- | --- | --- |
| `day_label_pattern`, `week_header_pattern` | Day-number pattern; workbook week pattern when omitted | Customize discovery with explicit regular expressions; these do not infer dates. |
| `style_header_labels`, `exercise_header_labels`, `variation_header_labels`, `sets_header_labels`, `reps_header_labels`, `rest_header_labels` | See the example and `ProgramConfig` in [program_models.py](../src/macrofactor_bridge/program_models.py) | Exact column-label lists for program discovery. Scoped batch profiles must retain shared discovery settings. |
| `week_pair_layout` | `null` when omitted | Must explicitly choose `plan_then_result` or `result_then_plan`; the example chooses the former and needs verification. |
| `prescription_source` | `selected_week` | `base` repeats the base prescription; selected weeks determine duration. |
| `base_cycle_count` | `null` | 1–52 explicit cycles only for base blocks without literal week headers; not a workaround for partial headers. |
| `sheet_order` | `left_to_right` | `right_to_left` changes discovery order, without inferring chronology. |
| `week_header_coverage_policy` | `intersection` | `aligned_union_base_only` requires base mode, explicit pair direction and a complete literal anchor. |
| `rest_range_policy`, `set_count_range_policy` | `block` | `upper` selects the supported range's upper bound with provenance. |
| `unitless_rest_policy` | `block` | `seconds` interprets only the base Rest column; ranges also need `rest_range_policy: "upper"`. |
| `allow_blank_targets`, `preserve_coach_notes` | `false` | Leave missing targets blank and retain instructions in exercise Notes; review the combined policy in the program guide. |
| `minimum_rep_policy` | `block` | `notes_only` requires both blank targets and preserved notes; does not invent a maximum. |
| `notes_mode`, `note_text_policy` | `full`, `verbatim` | `concise` trims repetition; `conservative` uses only the explicit text-cleanup allow-list. |
| `exclude_warmups`, `exclude_cardio`, `exclude_empty_days` | `false` | Opt-in exclusions with preview evidence; populated days cannot masquerade as empty. |
| `resize_template_workouts`, `use_day_designations` | `false` | Guarded row-group resize and reviewed day subtitles respectively. |
| `defaults` | Targets unset | `rep_min`, `rep_max`, `rir`, `rest_seconds`, and `set_type` never override coach values; rep bounds must be supplied together. |
| `color`, `icon` | `null` | Only directly verified values are accepted; see the program guide. |

Advanced per-exercise fields (`program_base_overrides`, `program_expansion`, `program_set_types`, `program_blank_rep_targets`, `program_notes`, inclusion/exclusion and availability flags) are explained with their guards in [reviewed corrections](Program-Generation.md#reviewed-corrections-and-concise-notes), [sequential expansion](Program-Generation.md#reviewed-sequential-exercises-from-one-row), and [import policies](Program-Generation.md#other-import-policies). Do not enable every optional policy at once; review each change in preview.
