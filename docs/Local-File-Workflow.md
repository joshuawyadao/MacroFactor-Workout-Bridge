# Local File Workflow

The project keeps personal workout files in `local-data/`, which is entirely excluded from Git. This provides a predictable place to drop new inputs and a local validation/version history without putting private workout data in repository history.

## Directory structure

```text
local-data/
├── inbox/
│   ├── coach/              # Drop new coach .xlsx workbooks here
│   └── macrofactor/        # Drop new exercise-log .csv or .xlsx exports here
├── archive/
│   ├── coach/              # Validated, hash-named coach workbook copies
│   └── macrofactor/        # Validated, hash-named exercise-log copies
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

## Recurring workflow

1. Save the latest coach `.xlsx` file into `local-data/inbox/coach/`.
2. Export the MacroFactor exercise log and save its `.csv` or `.xlsx` file into `local-data/inbox/macrofactor/`.
3. Validate and archive everything currently in both inboxes:

   ```bash
   PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace archive \
     --config config/exercises.local.json
   ```

4. Display the newest validated paths:

   ```bash
   PYTHONPATH=src python3 -m macrofactor_bridge.local_workspace status
   ```

5. Open MacroFactor Workout Bridge and select those archived files. Preview the selected worksheet, week, and explicit workout dates.
6. Save the generated workbook under `local-data/generated/workbooks/` and its JSON report under `local-data/generated/reports/`.

The archive command copies files; it never moves, changes, or deletes inbox files. An invalid file remains in the inbox, is recorded as an error in the run manifest, and is not copied into the archive.

## Version and validation history

Archive filenames use the intake date, a safe form of the original filename, and the first twelve characters of the SHA-256 content hash:

```text
2026-08-24--Coach_Program--59f565015e32.xlsx
```

Different file contents therefore create distinct versions even when the downloaded filename is reused. Dropping identical content again reuses the existing archive copy but still creates a new manifest recording that validation run.

Each manifest records:

- the full SHA-256 hash and byte size;
- the original inbox and archive paths;
- whether an existing identical archive copy was reused;
- coach worksheet, exercise-header, and week discovery;
- MacroFactor row count, workout date range, and exercise count;
- validation errors for anything not archived.

This is local version history, not a backup service. Back up `local-data/` separately if protection against disk loss is important.

## Privacy and safety

- The whole `local-data/` tree is ignored by Git.
- Personal exports, manifests, generated workbooks, and reports must not be force-added to Git.
- Only MacroFactor exercise-log exports belong in the MacroFactor inbox. Program exports do not contain the required exercise-log table and will fail validation.
- Keep using Preview before creating output. Archival validation does not authorize or perform workbook writes.
- The coach workbook and MacroFactor export selected by the app remain unchanged; output always uses a separate filename.
