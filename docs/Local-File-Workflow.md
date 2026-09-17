# Local File Workflow

The project keeps personal workout files in `local-data/`, which is entirely excluded from Git. This provides a predictable place to drop new inputs and a local validation/version history without putting private workout data in repository history.

## Directory structure

```text
local-data/
├── inbox/
│   ├── coach/              # Drop new coach .xlsx workbooks here
│   └── macrofactor/        # Drop new exercise-log .csv or .xlsx exports here
├── archive/
│   ├── coach/              # Validated, consistently named workbook copies
│   └── macrofactor/        # Validated, date-range-named exercise-log copies
├── current/                # Stable shortcuts to the inputs the app should use
├── generated/
│   ├── workbooks/          # Save completed coach workbook copies here
│   └── reports/            # Save preview/apply JSON reports here
├── annotations/            # Private workout-history block and week context
└── manifests/              # One validation manifest per archive run
```

Create or repair this structure at any time:

```bash
PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace setup
```

After an editable install, the shorter equivalent is:

```bash
macrofactor-workspace setup
```

Use `macrofactor-workspace --root /path/to/workout-data setup` for a custom location, and pass the same `--root` to `archive` and `status`. Setup and archive append managed-directory rules to the workspace's own `.gitignore` before creating data directories. Existing ignore content is preserved, and repeated setup is idempotent. This protects inboxes, archives, current links, generated files, annotations, and manifests even when the custom directory is inside a Git checkout. A symlinked `.gitignore` is refused rather than modified.

## Recurring workflow

1. Save the latest coach `.xlsx` file into `local-data/inbox/coach/`. Keep whatever filename the download already has.
2. Export the MacroFactor exercise log and save its `.csv` or `.xlsx` file into `local-data/inbox/macrofactor/`. There is no need to rename it.
3. Validate and archive everything currently in both inboxes:

   ```bash
   PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace archive \
     --config config/exercises.local.json
   ```

4. Display the newest validated paths:

   ```bash
   PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace status
   ```

5. To copy logged sets into a coach workbook, open MacroFactor Workout Bridge and choose the second top-level tab, **Update coach workbook**. Select `current/Coach Program - Current.xlsx` plus `current/MacroFactor Exercise Log - Current.csv` or `.xlsx`. These stable shortcuts are updated by the archive command. Click **Load workbook weeks**, select the worksheet and coach week, confirm the workout dates, then choose **Preview workbook changes**.
6. Click **Save updated workbook copy…** and save the new workbook under `local-data/generated/workbooks/`, with its JSON report under `local-data/generated/reports/`. Logged sets are copied into the selected week in this new workbook; the original workbook and export stay unchanged. This optional update is not required to use **Dashboard** or **Weekly feedback**.

## Dashboard workflow

### Automatic mode (0.9.1)

The app opens on **Dashboard**, the first top-level tab. With **Data → Auto-load inboxes** enabled, it discovers `local-data` beside the installed project, or remembers the folder you select with **Data → Choose workspace…**. It loads the local exercise mapping when present and the existing `annotations/workout-history.json`. You no longer need to choose an export on every launch. A remembered folder that disappears is an error, not permission to switch datasets.

Drop new exports in the corresponding inbox. On startup and after a managed-file change (checked every 30 seconds), background ingestion archives new content without modifying originals. Already-archived hashes are reused and unchanged refreshes create no empty manifests. The archive/current-link conventions above remain unchanged; dashboard selection is separate from the narrower current export used by **Update coach workbook**. **Refresh inboxes** also checks immediately. No MacroFactor API, download automation, or arbitrary Downloads-folder scan is involved.

**Source status…** reports why each source was selected, observed date ranges and completed sets, validation problems, and incompatible overlapping snapshots. A clean broad-history export is preferred as the baseline; the newest valid coach source is selected using its original modification timestamp. New dates and exact multiset supersets supplement the baseline. Repeated files do not duplicate workouts, and genuine identical repeated sets within one workout are retained. Conflicting day snapshots are flagged and not concatenated; an absent row is never treated as a deletion instruction. A newer narrow export does not erase prior coverage. The dashboard can be rebuilt from inboxes plus verified archived snapshots. Set details include file/row provenance; no merged CSV is written over an original.

**Weekly feedback** opens the export's latest mapped Monday–Sunday week. Use **Save training notes** to save the private annotation form. Background refresh pauses for unsaved feedback and checks again after saving. Explicit refresh can discard edits only after a default-No confirmation. If the annotation file changed externally, save is refused while your text remains available to copy. Invalid/newer files or a missing workspace leave previously loaded data visible with an explicit stale-data warning. All data stays local. To deliberately select one export instead, disable automatic mode; the standard manual controls become available.

### Dashboard views and manual selection

If selecting another workspace fails to load, the visible previous dashboard retains its source provenance and feedback-file conflict protection. An external edit to that previous feedback file still prevents a stale save; selecting a folder does not transfer ownership of the currently displayed notes.

The same external-change check protects **Save training notes** in manual mode. Turning automatic loading off never disables feedback-file protection; a stale manual form is refused and its unsaved text remains available to copy before reloading.

Version 0.9.1 places **Dashboard** first and **Update coach workbook** second. Within Dashboard, the main views are **Overview**, **Training timeline**, and **Exercise trends**. **Weekly feedback** stays in the compact toolbar, maintenance commands are under **Data**, and the clickable data indicator shows latest coverage and any conflict/notice counts. Click it for full source status and analysis warnings. Errors and refresh-paused notices remain visible. Use **Data → Select files manually…** to reveal manual inputs; enable **Auto-load inboxes** again to return to automatic mode. **More** contains **Block summaries**, **Compare blocks**, and **Training notes**; a selected secondary view stays visibly identified until you leave it. The presentation does not change calculations or stored files, and does not replace the installed app automatically.

The **Overview** is the initial Dashboard view. Main-lift cards show exact variations in consistent cyan/lavender/amber colors. Scroll horizontally through block cards and click a block heading to focus **Training timeline**, or a lift heading for the all-block timeline. Headings and exercise links replace repeated boxed action buttons, with keyboard access and visible focus retained. The timeline aligns three lift charts and all-exercise weekly workload, with saved-context markers that can be toggled. Click a chart week, or use the accessible week/exercise controls, to inspect the original logged sets and source rows. **← Overview** returns to the overview. Both views share range and variation choices. They scroll at smaller window sizes.

Block report averages use full Monday–Sunday weeks inside both the chosen range and the export's observed date bounds; the denominator is shown on each card. Partial weeks remain visible but are excluded from averages. Interior no-log weeks count as zero logged workload, not confirmed skips. Partial/outside-range and invalidly dated blocks are labelled; no unavailable average is replaced by zero. **Notes & exact values** expands saved notes, methodology, best estimates and weekly averages in a table. **Training focus** keeps sets/week bars visible by exercise, not muscle group: no unverified muscle attribution or hard-set assumption is applied. Saved notes do not imply inferred causes for load changes.

**Exercise trends** retains name search, family filters, chart metrics, and its independent all-history/4/12/24-week ranges anchored to the export's last workout week. Accessory workload buttons open this view. Earlier gaps and unmapped weeks remain visible; short exports prompt you to select all-time history. Full block/exercise tables are available in **Block summaries**, and the relative-week comparison is **Compare blocks**.

Cards display the selected variation's latest logged-week estimate in the selected range; the block table displays its best estimate per block within that range. These are different summaries, not recovery scores. Variations never combine automatically, and family navigation does not change aliases or workbook matching. Calendar shading does not create sets or infer skips. Saved context is descriptive only. Manual source changes clear the views; automatic updates replace them only after validation. Canonicalized set records are retained in memory for drill-down. No annotation-schema migration is required, and original exports/workbooks remain unchanged.

The initial variation choice follows its most recent workout date, not only its calendar week; equal dates use alphabetical ordering. Set details preserve accepted nonfinite source weights with an explicit invalid label so they can be inspected safely. Those values remain excluded from weight-based metrics, never converted to zero.

1. Keep an all-time MacroFactor exercise-log export in the private MacroFactor inbox. The archive can retain it alongside narrower weekly exports.
2. In the app's **Dashboard** tab, choose **Data → Select files manually…**, then select that all-time export directly, plus the newest coach workbook and local exercise mapping.
3. Use `local-data/annotations/workout-history.json` for the suggested private annotation file.
4. Load the dashboard to review calendar-week exercise trends and workbook worksheets as blocks. This step is read-only for both source files.
5. In **Training notes**, add block types, confirmed start dates, and optional week context gradually. A block without a confirmed date remains an ordered workbook summary and is not assigned dated MacroFactor workouts.
6. In **Compare blocks**, choose one exercise and two blocks with confirmed Monday starts. Review relative-week alignment, original labels/dates, per-exercise sets/days/loads, and saved context. Overlapping dates or ambiguous week labels must be corrected before comparison; the app does not guess a correction.

The comparison reads only the loaded history and saved annotations. Unsaved note edits do not appear until **Save training notes** reloads the dashboard. Existing annotation schemas and custom week layouts are unchanged. For a fresher comparison, choose the newer all-time export and click **Load history dashboard**; changing the source path invalidates the previous comparison immediately. No export is downloaded automatically.

Hover the summary/cards for detailed workout counts, duration, and RIR coverage. Select a block row and use **Edit training notes →**, or double-click the row, to open the correct block editor. **Swap A/B** reverses a comparison while retaining the exercise and metric; **Block notes…** opens full saved notes without shrinking the chart/table. Week context stays in table tooltips and the notes editor. Changing source paths clears the cards and comparison together. No data migration, new annotation fields, or source changes are required for this presentation update.

Missing exercise logs stay unavailable, not zero or confirmed skipped. Known skips can be written explicitly in week notes; the comparison displays that note without interpreting workbook Skip review markers as confirmations. A week outside the export's observed date range and the tail of a shorter block have separate labels. A partial date range is a coverage warning, not proof that workouts are missing. The chart uses a common scale including zero and breaks lines at missing values; no average-improvement ranking, recovery score, or deload prediction is produced.

The stable MacroFactor file under `current/` is selected for **Update coach workbook**: when exports end on the same workout date, the narrower later-starting export wins. It therefore may not contain all-time history. Automatic Dashboard loading consolidates managed snapshots independently; in manual mode choose the all-time inbox or archive file explicitly.

The annotation file stores worksheet names, optional block dates/types/notes, and optional week status, reason, affected movements, and notes. It does not copy set-by-set workout history. Vacation and injury are stored separately from accumulated fatigue so future analysis cannot silently reinterpret every reduced week as a recovery-driven deload. The file is replaced atomically, and a symlinked annotation destination is refused.

### Irregular coach week layouts

App version 0.4.1 supports an optional `week_layout` in each block's private annotation. Use it only after checking which source columns belong to that block. It is configured in JSON, not through a layout editor in the desktop app. Ordinary sheets still use automatically discovered numbered weeks in numeric order; **Update coach workbook** keeps its existing discovery behavior.

This synthetic example selects two normal headers and one date-labelled header, omitting any copied historical columns elsewhere in the worksheet:

```json
{
  "schema_version": 2,
  "blocks": {
    "Training Block": {
      "start_date": "2026-08-03",
      "week_layout": [
        {"label": "Week 10", "header_cell": "I3", "expected_header": "Week 10"},
        {"label": "Week 11", "header_cell": "K3", "expected_header": "Week 11"},
        {"label": "Week 12", "header_cell": "M3", "expected_header": "Train on 8/18"}
      ]
    }
  }
}
```

Array order is chronological, regardless of label numbering or column order. The first entry starts on the confirmed `start_date`; each next entry starts seven days later. A Monday start gives Monday–Sunday block weeks. Empty weeks remain in the calendar: absence of a logged workout does not shift dates, create a workout, mark a skip, or imply injury or fatigue. The block ends after its selected weeks; a worksheet title alone cannot add more weeks.

Each entry requires a unique non-empty label, an uppercase A1 header reference, and the exact header text (surrounding whitespace is ignored). A header must be a literal cell after the exercise header, anchored at the top left of its range if merged. Multi-row merged headers are supported, including single-column vertical merges. Results use the rightmost merged column, or the next column for an unmerged header. Duplicate result columns, results overlapping another selected header range, invalid anchors, missing configured sheets, and changed header text stop dashboard loading with a correction message.

Before editing, close the app and back up the annotation JSON privately. Preserve every existing block and week note; add the layout to the intended worksheet and set `schema_version` to `2`. Reload in version 0.4.1 or newer and verify selected week labels, counts, and date boundaries before saving further notes. Desktop block/week saves preserve the layout. Notes for excluded weeks remain stored but are not counted or shown in the selected-week editor. To correct a stale layout, inspect the current workbook and update the anchors/text deliberately; do not edit the source workbook just to satisfy the annotation.

Schema 1 files remain supported and remain schema 1 when saved without a layout. Files with layouts use schema 2, which older apps reject so they cannot silently discard this mapping. If reverting to an older app, restore the matching private annotation backup too; do not merely change the schema number. To return to automatic discovery in the new app, remove `week_layout` (or set it to `null`) and reload, understanding that copied numbered columns will be included again.

### Export context and archive behavior

When an `.xlsx` export contains MacroFactor's `Active Program` table, the preview reports non-empty exercise-level notes for exercises performed in the selected dates. This can carry context such as equipment choice or a misload explanation when entered in the exercise note. The current export's `Workout Log` table does not include program-level or session-level note columns, so those note types cannot be recovered. Reported notes remain review-only and are never inserted into coach result cells automatically.

The archive command copies files; it never moves, changes, or deletes inbox files. An invalid file remains in the inbox, is recorded as an error in the run manifest, and is not copied into the archive.

An exercise-log export must contain at least one usable completed set: a non-empty exercise and set type, with a positive finite rep count. Mixed exports can still be archived when some rows are incomplete; preview continues to report and skip those rows. Archival validation does not guarantee a matching, writable coach result cell.

Current and legacy MacroFactor pound exports are accepted through the exact `Weight (lb)` and `Weight (lbs)` header spellings. A weekly export can legitimately omit a workout because of its date window. When `workbook.empty_day_marker` is enabled, the bridge can place a yellow `Skip` review marker in the first available result cell of a programmed day with no matched session. The marker is not a MacroFactor skip record and must be confirmed during preview. It is withheld when unmatched, ambiguous, zero-rep, or otherwise unusable rows make the absence uncertain, and it never overwrites an existing result.

## Version and validation history

The archive command derives names from validated content rather than the uploaded filename. Every name begins with the UTC upload/intake date so versions are easy to search by when they were added. MacroFactor exports also include the first and last workout dates present in the export. Both file types end with the first twelve characters of the SHA-256 content hash:

```text
2026-08-24--Coach-Program--59f565015e32.xlsx
2026-08-25--2026-08-18_to_2026-08-24--MacroFactor-Exercise-Log--a57f84bd0ed1.xlsx
```

Searching an archive folder for `2026-08-25` finds everything uploaded on that date. Different file contents create distinct versions even when Downloads adds names such as ` (2)` or the same downloaded filename is reused. Dropping identical content again reuses its first upload-dated canonical archive copy but still creates a new manifest recording the later validation run. The exact original upload name and every intake timestamp are retained in manifests for traceability.

The `current/` entries are relative symbolic links, so they do not duplicate the workbook data. The tool updates only links it manages and refuses to overwrite a regular file at one of those names. For MacroFactor, the current link chooses the export with the latest workout date; when two exports end on the same date, it prefers the one with the later starting date. The current coach link chooses the most recently modified validated workbook.

History selection skips malformed manifest entries, invalid workout ranges, missing or invalid timezone-aware modification timestamps, and archive copies whose hashes no longer match. One damaged entry does not prevent the remaining valid history from being used.

You can move or restore the whole workspace, including `archive/`, `manifests/`, and the relative `current/` links. History and status resolve managed archive names beneath the current workspace root, even when older manifests contain absolute paths from the original location. The original workspace is never used as a fallback. Traversal paths and links that escape the managed archive directory are excluded from history selection.

Each manifest records:

- the full SHA-256 hash and byte size;
- the original filename, modification time, inbox path, and archive path;
- whether an existing identical archive copy was reused;
- the canonical files selected by the stable current shortcuts;
- coach worksheet, exercise-header, and week discovery;
- MacroFactor row count, workout date range, and exercise count;
- validation errors for anything not archived.

This is local version history, not a backup service. Back up `local-data/` separately if protection against disk loss is important.

## Privacy and safety

- The whole `local-data/` tree is ignored by Git.
- Custom roots also receive workspace-local ignore rules for every managed data directory. Ignore rules do not remove files already tracked or prevent force-adding files; audit existing Git history separately if private data was previously committed.
- Personal exports, manifests, dashboard annotations, generated workbooks, and reports must not be force-added to Git.
- Only MacroFactor exercise-log exports belong in the MacroFactor inbox. Program exports do not contain the required exercise-log table and will fail validation.
- Keep using Preview before creating output. Archival validation does not authorize or perform workbook writes.
- Treat every yellow `Skip` value as a review prompt. MacroFactor exercise-log exports do not distinguish a skipped day from an unlogged or out-of-range workout.
- The coach workbook and MacroFactor export selected by the app remain unchanged; output always uses a separate filename.
