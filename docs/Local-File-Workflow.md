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
├── reference/
│   └── macrofactor-program/ # Optional direct Export Program reference; manually managed
├── current/                # Stable shortcuts to the inputs the app should use
├── generated/
│   ├── workbooks/          # Save completed coach workbook copies here
│   └── reports/            # Save preview/apply JSON reports here
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

Use `macrofactor-workspace --root /path/to/workout-data setup` for a custom location, and pass the same `--root` to `archive` and `status`. Setup and archive append managed-directory rules to the workspace's own `.gitignore` before creating data directories. Existing ignore content is preserved, and repeated setup is idempotent. This protects inboxes, archives, current links, generated files, and manifests even when the custom directory is inside a Git checkout. A symlinked `.gitignore` is refused rather than modified.

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

5. Open MacroFactor Workout Bridge and select `current/Coach Program - Current.xlsx` plus `current/MacroFactor Exercise Log - Current.csv` or `.xlsx`. These stable shortcuts are updated by the archive command. Preview the selected worksheet, week, and explicit workout dates.
6. Save generated coach-workbook copies or MacroFactor program files under `local-data/generated/workbooks/` and their JSON reports under `local-data/generated/reports/`.

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

## Part 2 program preview and template gate

Coach-to-MacroFactor work starts with the read-only `program-inspect` and `program-preview` CLI commands documented in the README. Keep preview JSON under `local-data/generated/reports/`; it may contain private paths, coach text, exercise names, and mappings and must never be committed or attached to a public issue.

The `reference/macrofactor-program/` directory is optional and is not created, archived, selected, or validated by `macrofactor-workspace`. It is a private place to hold an `.xlsx` created specifically with MacroFactor **Program Settings → Export Program**. A granular Data Export workbook, Program Log, or `Active Program` sheet inside an exercise-log export is not a substitute. Keep the real reference read-only. The repository tests create their own synthetic structural fixture and never copy the real export or its values.

Pass the direct export to `program-preview --template` before generation. A valid template supplies a hash and schema result; an omitted, malformed, changed, or incompatible template keeps `generation_safe` false. `program-generate` accepts the same coach selection plus `--template` and a new `--output` path under `local-data/generated/workbooks/`. It refuses existing paths, differing periodized prescriptions, template shape/capacity mismatches, unsupported values, and every parser blocker. It preserves both private inputs byte-for-byte and validates that only the program worksheet and shared-string OOXML parts changed.

Coach week pairs require an explicitly verified direction. Use `program.week_pair_layout: "plan_then_result"` only when the left cell is the coach prescription and the right cell is the completed result; use `"result_then_plan"` for the reverse arrangement. The parser preserves the coach `Style` value but treats it as a MacroFactor set type only when the whole value is an exact supported set-type alias. It also stops a day at the first structurally blank separator after exercises begin, excluding later goals, notes, and reference sections from the program table.

For workbooks arranged newest-to-oldest, `program.sheet_order: "right_to_left"` starts the selection list at the last worksheet. Exercise category and detailed variation are read separately; add exact variation aliases or category/context mappings in an ignored private configuration when an older block uses different movements. A modern category-only mapping is not sufficient evidence for a different historical variation.

The README documents opt-in policies for standard sets, upper-bound rest ranges, blank targets, and preserving all coaching text in exercise notes. Those policies keep all workout days and optional exercises, and can exclude warmups/cardio before mapping checks. Preview still identifies set-count ranges, missing mappings, special set types, and template-shape gaps. Keep private mapping proposals separate from confirmed aliases, and do not publish either. The supplied template proves exercise notes; no session-note field is invented.

After explicit approval, `program.set_count_range_policy: "upper"` resolves supported base set-count ranges to their upper bound with visible provenance and retained range text in Notes. It does not resolve conflicting weekly counts, unsupported prose or excess template capacity. Keep approved mappings in a separate ignored Part 2 configuration so historical program choices do not change Part 1 mappings. The `+` symbols used to format completed myo-rep results in Part 1 are not evidence of MacroFactor program-file encoding.

A second read-only direct export has now verified mixed `Standard Set` / `Myo Set` values. Use exact-rule `program_set_types: ["standard", "myo", "myo"]` for an explicitly approved three-set sequence. `program_blank_rep_targets: true` leaves targets blank and requires coach notes preservation. These options affect Part 2 only. The small all-blank reference omits rep-range columns, so retain the earlier full-layout template for generation; do not substitute the sparse reference or infer drop-set/periodized structure from it. Keep the reference hash and generated candidate/reports private, and test the candidate manually before claiming compatibility.

When the number of days and set columns already fit, `program.resize_template_workouts: true` allows guarded resizing of the template's existing contiguous workout row groups. Each source and target day needs at least two exercises. Reference-bearing or irregular worksheet features remain blocked; the output retains row styles, headers and workout merges and is structurally re-inspected. This does not prove different cycle layouts or special-set encodings, and does not replace manual MacroFactor import verification.

The current verified schema contains one distinct cycle layout that MacroFactor repeats for the configured cycle count. For the initial coach program, use `program.prescription_source: "base"`: the base table supplies targets, while selected weeks determine duration. In base mode the CLI selects all safely discovered weeks when `--week` is omitted. Weekly updates remain separate private review data, not applied targets or exported notes. Apply later coach changes manually after review. The default selected-week mode continues to block conflicts and differing prescriptions; differing-cycle encoding is outside this workflow, not a required user setup step.

Use `program.use_day_designations: true` for the coach's subtitle beneath each day heading. Preview retains the original day identifier and source cell. Missing or ambiguous titles fall back to the original label. Verify the names for each selected block rather than reusing a modern block's labels for an older one.

`program.notes_mode: "concise"` removes redundant field dumps while the private report retains raw source text. Reviewed exact-rule `program_notes` may replace redundant variation text with residual coaching cues. Unresolved targets and unilateral instructions remain visible. Keep the original full-notes mode available.

Use `program.note_text_policy: "conservative"` only when a reviewed output should receive presentation cleanup. It applies an explicit typo/abbreviation allow-list, whitespace and sentence punctuation, and closes unmatched opening parentheses in exported exercise Notes. It never changes the coach workbook or the raw text/source-cell provenance stored in the private preview. It is not fuzzy correction and must not reinterpret targets. Omit it, or use `"verbatim"`, to preserve existing note text exactly.

A literal rep target may end in `again` or `here` (for example, `7 to 12 here`) and still become numeric targets. Any extra trailing words keep the text unsupported and visible for review; do not broaden that grammar to swallow prose.

When reviewing a coach variation, select an evidenced MacroFactor identity and preserve residual tempo, pause, speed, setup and technique instructions in exercise Notes. A cue-only difference need not become a new custom exercise. Record each reviewed choice as an exact variation/context mapping in a **new block-specific private profile**; this does not enable automatic similarity matching. Check all rows matched by that rule before replacing its variation notes. A material equipment, position or injury-related substitution still needs explicit evidence or a user choice. The verified template supports exercise Notes, not an assumed program/session-note field. Do not pull weekly updates or completed results into base-program notes.

The README describes `program_base_overrides` with exact expected-source guards, and `program_include_warmup` for narrowly approved inclusions. Keep these choices in ignored, block-specific configuration and leave Part 1 mappings unchanged. Per-set lists must match set counts; single numbers become equal bounds and `ea` means each side. Native minimum-only encoding is still unverified. If approved, set `program.minimum_rep_policy: "notes_only"` with `allow_blank_targets` and `preserve_coach_notes` true: exact `15` becomes `15 - 15`, while `15+ reps` stays in exercise notes with blank targets for manual entry. Preview shows the fallback explicitly. Do not mistake this for a verified minimum-only target or an invented upper limit.

When a reviewed correction is withdrawn, remove only that field from `program_base_overrides` (or the object if empty). Preview should return to `coach_base` provenance. Regenerate to a new path and verify that surplus set fields are cleared and unrelated prescriptions are unchanged. Do not edit the source workbook to undo a private configuration choice.

For an explicitly reviewed combined row, the README's `program_expansion` option creates two sequential exercises with separate exact names and sets each. It is base-mode only, guards both literal variation and set text, preserves shared instructions and exposes child/source provenance in CLI and JSON. Do not infer expansion from slashes, infer how to allocate per-set targets, or treat consecutive exercises as a superset. Keep child availability checks and all template gates. Leave the approved previous block's configuration and output unchanged when setting up a new block.

Small direct exports may verify exact exercise identities while omitting blank target columns. Inspect them read-only as identity evidence and retain a full-layout verified template for generation. The current next-block candidate still needs its own manual import feedback; approval of an earlier block is not a blanket compatibility claim. Desktop preview/generation are tracked in issues #17/#18 and owned by the existing dashboard workstream, with core conversion in #16. Reconcile branch/history changes before integration; do not create a second desktop shell or replace the installed app implicitly.

Choose optional `program.color` and `program.icon` in the ignored configuration. `Red` with `Rocket` is a verified growth-program theme; the README lists the limited verified tokens. Omission preserves the template's metadata. These settings affect the imported program appearance, not spreadsheet fills. Generate to a new path and verify cycles, named days, exercise inclusion, fixed reps, minimum notes, mixed set types and appearance in MacroFactor. Keep the draft PR and manual-validation issue open until the corrected candidate has been tested.

A structurally valid generated file is not proof of compatibility. Import it manually through MacroFactor **New Program → Import From File**, confirm the preview inside MacroFactor, and report whether the import succeeded before the project claims compatibility or adds the Part 2 desktop flow.

## Batch review through the newest program

Use the README's `program-batch` command for a one-shot right-to-left review after a previously reviewed worksheet/block. Keep the shared exact-mapping configuration, strict manifest and block-specific decisions in ignored private files. Never modify an approved earlier configuration to reuse it for later blocks. The manifest's `start_after` and `block_configs` use exact worksheet plus block keys; scoped configurations cannot silently alter discovery settings.

Choose a **new** run directory under ignored `outputs/`, outside read-only input locations. Preview-only is the default; `--generate` requests candidates for blocks passing parser, template and independent source/output checks. Discovery failures, unknown sheets, missing mappings and unsupported prescriptions are recorded while later blocks continue. Exit status 1 means the review is partial, not that safe later work was abandoned. Existing output directories are refused.

The batch checks all-day week coverage before using week count as program duration. A smaller shared intersection is not accepted as the whole block: inconsistent headers remain a blocker instead of producing too few cycles. An intentional partial-week export belongs in the existing single-block workflow.

If repeated day tables omit some labels but share a proved column layout, the optional `program.week_header_coverage_policy: "aligned_union_base_only"` can retain the full planned duration. It requires a complete literal anchor inside that block, consistent plan/result pairs and independent source verification. Set it in the shared and scoped configurations; it is invalid in selected-week mode. Missing or contradictory structural evidence still blocks the block. No workbook is edited to fill headers.

Keep activity evidence separate. Match coach weeks to actual calendar intervals before treating empty results plus no corresponding logged workouts as inactivity. The dated log must cover the interval; future weeks or intervals after its coverage remain unknown. Do not shorten a planned program solely because result cells or repeated headers are blank. Calendar/activity findings stay private, and the batch does not automatically remove inactive cycles.

For a coach who uses seconds without units, explicitly set `program.unitless_rest_policy: "seconds"` in new private profiles. It applies only to literal base Rest cells, leaves weekly numbers untouched and reports the assumption with distinct provenance. Rest ranges still need the upper-bound policy. Per-side set counts are not doubled, and native supersets give each explicitly mapped movement the whole listed count. Preserve earlier sequential profiles unchanged. A new full-layout five-set reference clears capacity only for up to five sets; blank RIR values are acceptable, missing RIR headers are not.

Start with `review.md` for block status, exception counts, mapping/decision questions and technical findings. `summary.json` and per-block JSON preserve every original diagnostic and source location, including any abbreviated technical-location lists. A source-coverage finding may be an auxiliary table beyond the program's blank separator; it requires boundary review, not automatically adding that row as an exercise. Do not turn all exceptions into user questions or approve new aliases from similarity alone.

After read-only structural inspection, `reference_boundaries` can record a block-specific exact merged reference heading. The README lists its strict structural guards. It never skips preceding blank gaps or preceding stray rows, and a changed/missing heading fails closed. Keep the literal marker in the private manifest, not a shared code constant or public issue.

The run preserves input/config/evidence hashes and retains candidates temporarily until final validation. Global input changes stop further processing and invalidate the candidates. A safe historical candidate is **automated-checked**, not **app-tested**. The manual plan asks for uncovered structural/identity representatives plus the newest program; it never silently substitutes an older program when the newest is blocked. Different row shapes, durations, special sets or custom identities can still require additional representative imports.

Only record `manual_import_evidence` after the user confirms that exact file imported successfully. Keep its path/hash and the declaration private. An earlier structural match never establishes that an unknown custom exercise exists in the user's database, and no new file inherits manual-verification status. Once consolidated mapping and format questions are resolved, rerun into a different directory; never overwrite or force-add the earlier reports. Part 1 and desktop/dashboard work remain unchanged.

## Privacy and safety

- The whole `local-data/` tree is ignored by Git.
- Custom roots also receive workspace-local ignore rules for every managed data directory. Ignore rules do not remove files already tracked or prevent force-adding files; audit existing Git history separately if private data was previously committed.
- Personal exports, manifests, generated workbooks, and reports must not be force-added to Git.
- Direct MacroFactor program-export references and any derived private schema notes also remain local and must not be force-added to Git.
- Only MacroFactor exercise-log exports belong in the MacroFactor inbox. Program exports do not contain the required exercise-log table and will fail validation.
- Keep using Preview before creating output. Archival validation does not authorize or perform workbook writes.
- Treat every yellow `Skip` value as a review prompt. MacroFactor exercise-log exports do not distinguish a skipped day from an unlogged or out-of-range workout.
- The coach workbook and MacroFactor export selected by the app remain unchanged; output always uses a separate filename.
