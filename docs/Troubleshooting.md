# Troubleshooting

[Documentation index](README.md) · [Project home](../README.md)

Start with the preview's **Review needed** panel or **Data → Source status…**. They explain what was selected, what was withheld and which source needs attention. Preserve the original files while correcting your mapping or selections.

## Setup and loading

| Symptom | Check and next step |
| --- | --- |
| `No module named macrofactor_bridge` | Run from the repository root with `PYTHONPATH=src`, or use `.venv/bin/macrofactor-bridge` after an editable install. |
| Missing `exercises.local.json` | Create it once from the example, then review the exact mappings. See [Configuration](Configuration.md). Do not overwrite an existing personal copy. |
| App does not find the workspace | Use **Data → Choose workspace…** and select the `local-data` directory. A missing remembered folder is reported instead of silently choosing another dataset. |
| New Downloads file does not appear | Put it in the appropriate inbox. The app does not scan Downloads. Enable **Auto-load inboxes** and use **Refresh inboxes**. |
| Missing or duplicate export columns | Use an exercise-log export with the [required headers](Getting-Started.md#what-you-need). Program exports are a different format. Do not rename units to bypass validation. |
| Build fails to install a wheel | Use the documented Python/platform baseline and check network access. Locks restrict accepted wheels; do not remove hashes or unpin packages to make a build pass. See [Development](Development.md). |
| macOS blocks a copied app | The project has no notarized download. Prefer a local source build. For a copy you trust, use macOS's normal approval flow; do not disable system protections globally. |
| An update seems absent | Source updates do not replace installed bundles. Follow [app update steps](Local-File-Workflow.md#updating-the-local-app-after-a-merge); record the source commit, not only the version label. |

## Workbook preview and output

| Symptom | Meaning and next step |
| --- | --- |
| No worksheets or weeks | Confirm configured exercise headers and week pattern with `inspect`; `.xlsm` is unsupported. A discovered week must point to the intended result column. |
| Unmatched exercise | Add a confirmed exact `source_aliases` / `coach_aliases` mapping. Similar names are not matched automatically. Preview again after editing. |
| Multiple matching workbook rows | Use a verified `coach_context_aliases` value from the same row to disambiguate. Do not force a selection based on row order. |
| Multiple sessions for one exercise | Narrow the inclusive date range or review the sessions separately. Part 1 refuses to merge ambiguous sessions. |
| Existing or absent result cell is skipped | Existing values/formulas are protected; completely absent worksheet cells lack a trusted style. Inspect the intended coach template instead of treating a skipped row as a successful transfer. |
| Invalid weight/reps or partial results | Nonfinite values withhold the affected target, including shared supersets; unrelated cells may still be writable. Review source-row diagnostics. Invalid values do not become zero. |
| Yellow `Skip` marker | A review prompt for a programmed day with no matched session. Confirm the date window and actual activity before sharing; it is not a MacroFactor skip record. |
| Source or mapping changed after preview | Generate a new preview using the intended files and effective transfer settings. Program-only settings do not invalidate a Part 1 preview. |
| Output/report already exists | Choose a new filename. Inputs, existing outputs and symlink aliases are protected. Reports also cannot use an input/mapping/workbook destination. |
| No proposed writes | Nothing is eligible for transfer under this selection; apply refuses to create an empty output. Review dates, mapping and occupied-cell diagnostics. |

Normal blank/bodyweight loads format as zero; nonfinite numeric values are different and are withheld. Reps stay as exported when a confirmed per-side weight rule is applied. See [result formatting](CLI-Reference.md#result-formatting) and [output safety](Local-File-Workflow.md#preview-output-and-report-safety).

## Dashboard and feedback

| Symptom | Meaning and next step |
| --- | --- |
| History is too short | Add an all-time export. The app cannot recover workouts absent from every supplied snapshot. Current weekly shortcuts and Dashboard history use different selection policies. |
| Overlap conflict in Source status | Two exports disagree about the same day's sets. Inspect provenance and use a deliberate manual export override when resolving it; snapshots are not blindly combined. |
| Block has no mapped history | Confirm its Monday start, distinct nonempty week labels and nonoverlapping dates. Calendar history stays visible while invalid blocks await correction. |
| Weekly feedback opens an earlier week | It opens the newest **mapped** logged week. If recent workouts are unmapped, confirm block dates. Existing unsaved feedback keeps its current selection. |
| No block average, or a gap in a chart | Coverage may be partial, dates invalid, or sets absent. Missing is not zero; only full covered weeks enter workload averages. Inspect the selected range and exact variation. |
| Refresh waits | Save your unsaved training notes first. Explicit refresh offers a discard confirmation; automatic refresh does not discard edits. |
| Saving notes reports an external change | Keep/copy your unsaved text, inspect the newer annotation file, then reload and reconcile deliberately. Stale forms cannot overwrite newer notes. |
| Old dashboard remains after a load failure | The previous view is retained with a stale-data warning. Check Source status and correct the missing/invalid input before relying on it. |
| Custom week layout no longer loads | Back up annotations and verify exact workbook header text/anchors. Follow [irregular layouts](Local-File-Workflow.md#irregular-coach-week-layouts); do not change source headers merely to satisfy stale annotations. |

## Program generation

| Blocker | Next step |
| --- | --- |
| Direct program export required | Supply an actual **Export Program** `.xlsx` with `--template`. An exercise log or Active Program sheet cannot prove the program schema. |
| No safe plan weeks | Verify `program.week_pair_layout` against the coach workbook. Only a fully headerless base block may use explicit `base_cycle_count`; partial/contradictory headers remain blockers. |
| Unsupported prescription | Review raw source text and supported policies in [Program generation](Program-Generation.md). Do not invent targets or rely on fuzzy interpretations. |
| Source row beyond a blank separator | Inspect the full day table and any auxiliary reference section. An exact reviewed batch boundary must satisfy structural guards and cannot hide earlier omitted exercises. |
| Shape/set-capacity mismatch | Use an evidenced full-layout template with sufficient capacity. Guarded resizing cannot add days or set columns. Blank targets still need their required headers. |
| Different prescriptions across cycles | The verified repeated layout requires identical prescriptions. Use base mode only when it represents the intended initial program; weekly progression remains separate. |
| Batch exits with `1` | Read `review.md`, then per-block JSON for all diagnostics. Later blocks may have completed; a partial run is not blanket success. Rerun into a new directory after reviewing decisions. |
| Automated checks pass | Manually import the exact generated file and inspect MacroFactor's preview. Structural validation and representative sampling do not prove every new candidate imports. |

## Reporting a reproducible problem

Include the source commit or app build provenance, operating system, Python version when relevant, command or UI steps, and the error text. Reproduce with synthetic data where possible. Do not attach real workbooks, exports, manifests, reports, mappings, annotations or unredacted paths to public issues.

Use [GitHub issues](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/issues) for ordinary bugs. Follow the [Security Policy](../SECURITY.md) for vulnerabilities and private-data exposure. Contributor test failures and long-running sessions are covered in [Development](Development.md).
