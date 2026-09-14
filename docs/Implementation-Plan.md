# Plan

Build the first read-only workout-history milestone inside the macOS app, using coach worksheets as blocks and MacroFactor exercise-log exports for dated exercise trends. Add optional RIR and workout-duration ingestion plus private local annotations for block dates/types and deload, vacation, injury, or modified weeks, while deliberately withholding predictive recovery or deload claims.

## Scope
- In: a desktop History dashboard, workbook block/week discovery, calendar-week exercise summaries, conservative estimated-1RM trends, optional RIR and duration metrics, local JSON annotations, block/date linking when a start date is known, synthetic tests, user documentation, and app version metadata.
- Out: automatic deload prediction, medical or injury advice, wearable/health integrations, nutrition or bodyweight overlays, automatic inference of undated block starts, modification of source exports or coach workbooks, and committing personal workout data.

## Action items
[x] Extend the MacroFactor import model and CSV/XLSX readers to preserve optional workout duration and actual RIR values without requiring either field.
[x] Add a history-analysis module that discovers workbook sheets as ordered blocks, summarizes completed workbook weeks, groups dated MacroFactor sets into exercise/week trends, reports RIR coverage, and maps workouts into annotated block dates without guessing missing dates.
[x] Add a validated, atomically written local annotation store for block type/start date and week status/reason/affected movements/notes, with vacation and injury represented distinctly from fatigue-driven deloads.
[x] Add a read-only Workout History tab to the PySide app with source selection, overview metrics, block summaries, exercise trends, explicit confidence/limitations, and controls for saving private block/week annotations.
[x] Add focused synthetic importer, analytics, annotation-storage, and offscreen GUI tests, including missing RIR, repeated session duration, unknown block dates, mapped block weeks, and vacation/injury annotations.
[x] Update the README and local-file workflow for the dashboard, annotation privacy, RIR limitations, block-date behavior, and non-predictive recovery boundary; advance the app to version 0.4.0 build 5.
[x] Run targeted tests, the complete `./scripts/test.sh` suite, source compilation, `git diff --check`, source-GUI smoke testing, real-data read-only verification, and default-size visual inspection. The initial rebuild reached the macOS bundling step but stopped when Apple's `lipo` tool reported an unaccepted Xcode license; the release-validation follow-up below resolved and rechecked that environment dependency.
[x] Review and save the scoped milestone on `codex/workout-dashboard-mvp` with no private exports, workbooks, reports, annotations, virtual environments, build directories, or generated app artifacts included.

## Release validation follow-up
[x] Accept the installed Xcode license with administrator authorization and confirm `xcodebuild -license check` succeeds.
[x] Rebuild `dist/MacroFactor Workout Bridge.app` from the pinned dependency lock using `./scripts/build_macos_app.sh`.
[x] Verify the packaged app has a valid ad-hoc signature, version `0.4.0` build `5`, an arm64 executable, and a passing embedded-GUI smoke test.
[x] Save and push the completed release-validation record without staging the ignored build environment or generated app bundle.

## Open questions
- None.
