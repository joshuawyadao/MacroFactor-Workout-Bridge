# Desktop guide

[Documentation index](README.md) · [Project home](../README.md)

Complete [Getting started](Getting-Started.md) before your first session. The app has two top-level tabs; program generation is a separate [CLI workflow](Program-Generation.md).

| Control | Use it for |
| --- | --- |
| **Dashboard** | History, trends, block context and weekly feedback |
| **Update coach workbook** | Preview completed sets and save a new workbook copy |
| **Data** | Workspace selection, automatic loading, manual files and source status |
| **Weekly feedback** | Open the newest logged week mapped to a valid coach block |
| **More** | Block summaries, comparisons and training notes |

**On this page:** [Automatic loading](#automatic-inbox-loading) · [Charts](#dashboard-and-timeline) · [Manual history](#manual-history-review-and-interpretation) · [Workbook transfer](#update-a-coach-workbook).

After a local build, the application is at:

```text
dist/MacroFactor Workout Bridge.app
```

Open Finder, navigate to `dist`, and double-click **MacroFactor Workout Bridge**. The app is self-contained; using the built app does not require Python or Terminal.

Version 0.9.1 opens on **Dashboard**, the first top-level tab, automatically loaded from your managed folders. **Update coach workbook** is the second tab; it copies logged sets into the selected coach week in a new workbook and is not required for dashboard analysis or weekly feedback. Neither workflow modifies the original export or coach workbook. **Weekly feedback** stays visible; **Data** holds file/loading tools, and **More** holds secondary analysis views. Squat is cyan, bench lavender, and deadlift amber on black/charcoal surfaces. Keyboard focus and hover states keep the quieter controls discoverable. The theme is dark-only, independent of the system appearance. Yellow `Skip` review markers retain dark text for readability.

## Automatic inbox loading

Keep coach workbooks in `local-data/inbox/coach/` and MacroFactor exercise-log exports in `local-data/inbox/macrofactor/`. The app discovers a `local-data` workspace beside its project installation (including `dist/*.app`), or remembers the folder chosen with **Data → Choose workspace…**. It prefers `config/exercises.local.json` beside that workspace, otherwise the bundled example mapping, and uses `annotations/workout-history.json` for feedback. A missing remembered folder is reported rather than silently switching to another dataset.

**Data → Auto-load inboxes** is enabled on normal first launch. New inbox content is validated and archived as immutable, content-deduplicated snapshots; unchanged launches do not create empty manifests. No originals are moved or rewritten. Background checks every 30 seconds detect managed-file changes; **Data → Refresh inboxes** checks immediately. Downloads and arbitrary folders are not scanned. **Data → Select files manually…** turns automatic loading off and reveals the manual source selectors. App preferences remember only the workspace and automatic-mode choice, not workout contents. Smoke tests do not run ingestion.

**Source status…** explains the selected coach workbook, broad-history baseline, latest workout coverage, every contributing export, and any skipped/corrupt inputs or overlap conflicts. Coach selection uses the newest valid source modification timestamp retained by archival, not filename guessing. Baseline ranking prefers clean imports, more logged dates, broader date span, more completed sets, then latest workout/modified date. These are coverage indicators, not a guarantee of complete logging. A newer narrow export supplements earlier history instead of replacing it. Exact duplicate day snapshots count once; identical repeated sets *inside* a workout remain separate. Exact supersets replace smaller day snapshots. Conflicting weight/reps/RIR/duration or workout identities keep the higher-ranked snapshot and appear for review; absent rows are not inferred deletions. Use a deliberate manual export override when resolving conflicting snapshots. There is no stable export set ID, so conflicting days are never blindly concatenated.

Click **Weekly feedback** to open the most recently logged, mapped coach week. Save using **Save training notes**. Automatic refresh waits while the form has unsaved edits; an explicit refresh offers a default-No discard confirmation. External changes to the feedback file are detected before saving so stale edits cannot silently overwrite newer notes. Failed refreshes retain the previous view with a visible warning, and results from an obsolete workspace/mode are ignored. The compact data indicator shows latest coverage and conflict/notice counts; click it or choose **Data → Source status…** for full provenance, current status, and analysis warnings. Routine diagnostic prose is hidden from the overview, not removed. Set drill-down includes source file and source row; consolidation is rebuilt from local snapshots, not uploaded to a server.

## Dashboard and timeline

Within **Dashboard**, the main views are **Overview**, **Training timeline**, and **Exercise trends**. **More** opens **Block summaries**, **Compare blocks**, or **Training notes**; the selected secondary view appears as a tab until you leave it. Weekly feedback and drill-down links use the same navigation, preserving unsaved form text. This presentation update does not change source selection, calculations, stored data, or the installed app automatically.

### Overview and workload

The **Overview** shows squat, bench, and deadlift charts, a horizontally scrollable row of compact coach-block cards, and exercise-workload bars. Quiet lift/block headings with arrows open their timelines; they remain keyboard-operable with visible focus. Each lift defaults to its most recently logged supported variation and names it explicitly; use its understated dropdown to choose another. Family lists are navigation groups, not combined strength metrics. Each headline is the estimate from the latest logged week in the selected range for that variation, not necessarily the latest export week. Expand **Notes & exact values** for saved context, methodology and the table of best per-block estimates and normalized weekly workload. Blank estimates are unavailable, not zero. Reduced loads do not imply fatigue.

Block cards show average logged sets and distinct training days per week, the number of full weeks used, and explicit coverage labels. Averages include only full Monday–Sunday weeks within the selected range, observed export date bounds, and block dates. Interior weeks with no logs contribute zero *logged workload*, not a confirmed skip. Partial boundary weeks remain in charts and performance summaries but are excluded from averages; partial blocks are not ranked against complete ones. Undated, overlapping, or non-Monday blocks do not receive invented averages. **Training focus** ranks exercises by average logged sets per full week in the selected range, not by muscle growth, hard sets, or intensity. Muscle attribution remains deferred until an explicit exercise-to-muscle mapping is available.

### Training timeline

Click a main-lift heading to open **Training timeline**, or a block heading to focus the timeline on that block. The three exact-variation charts share calendar dates and block shading, followed by an all-exercise workload bar chart. Range and variation selections are shared with the dashboard; all-history/4/12/24-week ranges end in the export's latest week, not today. **Show saved context** toggles dotted markers and context text without changing values or removing weeks. Missing logs stay gaps. Click a chart week to inspect original sets, or use **Inspect a week**, the exercise dropdown, and **View logged sets** with the keyboard. The read-only dialog shows workout/date, canonical exercise, set type, original load/reps/RIR, and source row; names use the existing alias configuration but loads are not coach-converted. Sets are retained in memory only, and source changes close stale dialogs. Use **← Overview** to return. Smaller windows scroll vertically to keep every chart accessible.

### Exercise trends

Open **Exercise trends** for searchable analysis of any exercise, including accessories. Accessory workload buttons open this view directly. Search by name, optionally narrow to a main-lift family, and choose its independent all-history/4/12/24-week range and metric: estimated 1RM, top weight, sets, or training days. No block selection is required. Missing weeks remain gaps, unmapped weeks stay visible, and boundary weeks flag partial export coverage. Hover the chart for dates/values and table cells for full saved context. Named variations are never silently combined.

### Block summaries and comparisons

**Block summaries** retains the overview totals and full-width block/exercise tables with a draggable divider. Select a block and click **Edit training notes →** (or double-click its row) to open its notes editor. **Compare blocks** remains available for explicit relative-week A/B comparisons: its first load chooses an exercise with the broadest useful coverage across the initial A/B pair, while later reloads preserve an available exercise you selected. Use **Swap A/B** and **Block notes…** as before. Loading or exploring never saves annotations automatically; changed sources clear every history view, and reloading preserves available selections/filters. Short exports get a prominent all-time-history hint on the dashboard.

The exercise explorer's chart runs chronologically; its detail table lists the newest weeks first so recent training is visible without scrolling through the year.

Default variation selection uses the most recent actual workout date, including when two variations were trained in the same calendar week; equal dates use alphabetical ordering. Original-set details label nonfinite source weights as invalid while retaining their exported value for inspection. They do not become zero or enter strength/load calculations.

## Manual history review and interpretation

The first top-level tab, **Dashboard**, supports history analysis and weekly feedback without running **Update coach workbook**. Automatic mode follows the workflow above; for a manual override, turn **Auto-load inboxes** off:

1. Choose an all-time MacroFactor exercise-log export, the newest coach workbook, and the exercise mapping.
2. Leave the suggested private annotation path under `local-data/annotations/`, or select an existing annotation JSON file.
3. Click **Load history dashboard**. The overview reports usable sets, workout and training-day counts, RIR coverage, and workout duration without changing either source. Loaded source controls collapse to leave room for analysis; click **Show sources** to choose different files.
4. Review coach worksheets as blocks in their existing Excel tab order. Each block reports its discovered weeks and populated result cells.
5. Choose an exercise to review calendar-week training days, sets, top load, Epley estimated 1RM, volume load, average recorded RIR, and a compact estimated-strength trend.
6. Optionally confirm a block type and start date, then annotate a coach week as normal, deload/re-entry, or modified. Reasons distinguish planned or fatigue-driven changes from vacation, injury, illness, and other context.
7. Optionally, in **Compare blocks**, select one exercise and two different blocks. The chart shares one scale for A and B; choose estimated 1RM, top weight, logged sets, or training days. Paired rows retain each coach week label and its Monday–Sunday dates, alongside saved week context. Hover over a context cell to read its full notes; long notes do not expand rows. Edit context in **Training notes** and save to refresh the comparison.

Comparisons align relative week 1 with week 1, even when the coach labels start at a different number. Shorter blocks are not padded with invented training. Missing exercise logs appear as `No logged sets`, with unavailable metrics shown as dashes and gaps in the chart—not zeroes or confirmed skips. A logged zero remains zero. Weeks outside or partly within the export's observed date range are labelled accordingly; that range does not prove workout completeness. Known skips can be recorded explicitly in week notes; workbook `Skip` review prompts are not treated as confirmations.

Block comparisons require confirmed Monday starts, distinct week labels, and date ranges that do not overlap any other dated block. The app explains invalid selections without changing dates or source files. It compares the same canonical exercise only, does not combine similar movements, and does not rank blocks of different lengths or infer recovery from reduced training. Block types, notes, and vacation/injury context remain descriptive. Reloading preserves comparison selections when they still exist; changing source paths clears stale results until the next successful load.

Block dates are never inferred from worksheet names or gaps in training. Until a start date is confirmed, dated workouts remain visible by calendar week but are not assigned to that block. Assignment requires a confirmed Monday start, nonempty distinct week labels and no overlap with another dated block. Only then do consecutive seven-day ranges map to the workbook's discovered week labels. Invalid dates or labels stay editable and leave sets visible in calendar history with zero block attribution; comparisons and summaries use the same validity rule. A missing workout never shifts later weeks or becomes an inferred skip.

For irregular worksheets with copied historical columns or date-labelled weeks, an optional private `week_layout` selects the exact headers in chronological order. Counts, date ranges, and the week-note selector then use only those weeks. Source headers are checked on every load, and a changed or missing header stops loading rather than silently remapping history. Week discovery in **Update coach workbook** is unchanged. See [custom history layouts](Local-File-Workflow.md#irregular-coach-week-layouts) for the advanced JSON configuration and version requirements.

Estimated 1RM is a descriptive Epley estimate from weighted standard sets of 1–12 reps. Drop, mini, and myo sets are excluded from that estimate; all completed positive-rep sets still contribute to set, repetition, and per-exercise volume summaries. It is not an injury assessment, readiness score, work-capacity prescription, or deload prediction.

MacroFactor's `RIR` and `Workout Duration` columns are optional. RIR coverage is reported rather than imputed, and numeric workout duration is interpreted as seconds and counted once per workout even though the export repeats it on each set row. The export does not contain a separate actual-RPE column.

## Update a coach workbook

The second top-level tab, **Update coach workbook**, guides the optional workbook-copy workflow:


1. Choose the MacroFactor `.csv` or `.xlsx` exercise-log export.
2. Choose the coach `.xlsx` workbook.
3. Use the bundled exercise mapping, or save an editable JSON copy and select it.
4. Click **Load workbook weeks**, then select the worksheet and coach week.
5. Confirm the inclusive workout dates. **Use latest export week** selects Monday through Sunday around the export's latest workout row; it does not infer that an absent workout was skipped.
6. Click **Preview workbook changes** and inspect the proposed-change table and **Review needed** panel. Yellow `Skip` rows call out programmed days with no matched session and must be confirmed before sharing.
7. Click **Save updated workbook copy…** and choose a new `.xlsx` filename. The logged sets go into the selected week in this new copy; the original workbook stays unchanged.
8. Optionally save the full review and validation report as JSON at a new path. Desktop and CLI refuse existing files, source/mapping paths, and generated-workbook paths, including symlink aliases.

If the workbook, export, or Part 1 mapping settings change after preview, create a new preview before applying. Program-only mapping settings do not invalidate a Part 1 review.

The bundled mapping is an example, not a promise that every personal exercise name is configured. Use **Save editable copy…** to create a normal JSON file outside the repository, add exact aliases and confirmed conversions, then preview again. The app never edits the mapping stored inside its bundle.


## Interpreting a partial result

A blank metric means unavailable data, not zero. A shorter export limits observed coverage; an empty result cell or calendar gap cannot confirm a skipped workout. Confirm block dates and inspect original sets before interpreting trends. The [troubleshooting guide](Troubleshooting.md#dashboard-and-feedback) explains missing blocks, conflicting snapshots and protected feedback saves.

For storage, annotations, custom week layouts and backups, see [Local File Workflow](Local-File-Workflow.md).
