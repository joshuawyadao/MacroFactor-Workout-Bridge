# Batch program review

[Documentation index](README.md) · [Project home](../README.md)

Read the [single-block program guide](Program-Generation.md) first. Use this workflow after confirming reusable mappings and reviewing the supplied template.

**On this page:** [Run a batch](#run-a-batch) · [Manifest](#manifest-and-scoped-configurations) · [Week coverage](#week-coverage-and-reference-boundaries) · [Audits](#audits-and-publication) · [Import evidence](#manual-import-evidence).

## Run a batch

`program-batch` is a one-shot, local CLI workflow for repeated **base** programs. It visits worksheets in the configured order, continues past blocked blocks and writes one private review instead of requiring an import attempt for each block. Worksheet order is chronology only when configured that way; dates are not inferred.

```sh
PYTHONPATH=src python3 -m macrofactor_bridge program-batch \
  --workbook "/path/to/Coach_Program.xlsx" \
  --config reports/shared-program-mappings.local.json \
  --template "/path/to/Direct_Program_Export.xlsx" \
  --manifest reports/program-batch.local.json \
  --output-dir outputs/coach-batch-001 \
  --generate
```

Omit `--generate` to preview/audit only. The output directory must be new, including for preview-only runs. Each run contains `summary.json`, `review.md`, per-block JSON and, only for passing blocks, generic `block-NNN.xlsx` candidates. These files contain private information and must stay ignored. Exit codes are **0** for all selected items ready/generated/explicitly skipped, **1** for a partial or input-invalidated run, and **2** for fatal setup/configuration failures. A blocked or unrecognized sheet remains visible; it is never silently treated as completed.

The shared configuration must use `program.prescription_source: "base"` and contain only reusable exact mappings and general policies. Reviewed corrections, residual notes, expansions, special-set sequences, exclusions, warmup inclusions and supersets belong in separate block-scoped configurations. Copying an older block's complete configuration into the shared file is refused. New aliases are never guessed or written automatically.

During human review, a known exercise can represent a tempo, pause or speed variation while `program_notes` retains those residual coaching cues. Save the decision as an exact variation/context rule in a new private block profile; the runtime still does no fuzzy matching. Review materially different equipment, body position or injury substitutions separately. The verified export has **exercise Notes**; do not invent program/session-note fields or include completed results and unapplied weekly updates in base-program notes.

## Manifest and scoped configurations

The optional private manifest has a strict schema. Paths inside it are relative to the manifest. Block identifiers are local to a worksheet, so every selection uses both exact strings:

```json
{
  "schema_version": 1,
  "start_after": {"sheet": "Previously reviewed worksheet", "block": "block-1"},
  "block_configs": [
    {"sheet": "Selected worksheet", "block": "block-1", "config": "selected-program.local.json"}
  ],
  "reference_boundaries": [
    {"sheet": "Selected worksheet", "block": "block-1", "marker_text": "Reviewed reference heading"}
  ],
  "skip_sheets": [
    {"sheet": "Reference only", "reason": "Explicitly reviewed as not a program"}
  ]
}
```

All fields except `schema_version` are optional. Scoped configs are complete configurations, not patches, and must retain the shared discovery settings. Unknown keys, unknown selections, duplicate overrides and implicit skips are rejected. Missing/invalid scoped configuration blocks its item while later items continue. Every safely discovered week determines one repeated cycle; the batch does not interpret weekly prose as updated prescriptions.

## Week coverage and reference boundaries

Because a batch requests the whole block, the independent audit requires complete week coverage across days, not just their shared intersection. Inconsistent week headers or omitted cycles block that item instead of silently shortening the program. Use the existing single-block preview for an intentionally limited week selection.

For repeated base tables with omitted week labels, `program.week_header_coverage_policy: "aligned_union_base_only"` opts into guarded alignment. It requires base mode, explicit plan/result direction, a complete literal anchor day within the same block, and consistent non-overlapping column pairs. It fills missing layout metadata only; it never changes the workbook or uses completed results as prescriptions. Conflicting labels, shifted pairs, formulas or unproved geometry remain blocked. The independent audit checks the aligned full week set and raw planned cells. The default `"intersection"` behavior is unchanged; all scoped batch configs must share this discovery setting.

Planned cycles and performed activity are different facts. A blank coach result cell does not prove inactivity. An empty historical week may be reviewed as not worked only with established calendar alignment and exercise-log coverage for that interval; a log ending before the interval cannot prove absence. Missing repeated headers must not be used to shorten duration. This workflow does not automatically infer vacation dates or remove cycles based on absent activity.

Set capacity comes from the supplied direct template, not a hard-coded maximum. A verified five-set full-layout reference is supported without adding columns; all five Type/Rep Range/RIR/Rest headers are required even when values are blank. Smaller prescriptions clear unused slots, while prescriptions exceeding that template's capacity remain blocked. A larger reference does not establish manual import success for any new candidate.

`reference_boundaries` is an opt-in **reviewed** auxiliary-section boundary, not a guessed end row. Its exact literal must occur once after the final day heading in that block, in a single-row merge spanning style and variation/exercise columns, with blank prescription fields and a preceding blank base row. Formula, stale, duplicate or malformed markers block. The source audit still scans across every earlier blank gap; this cannot hide an omitted exercise before the marker. Leave it absent until that reference section has actually been inspected. No private heading is built into the application.

## Audits and publication

Two separately implemented checks supplement the existing service validations:

- The **source audit** checks day/row coverage, exact mappings, literal numeric prescriptions, raw provenance, configured policies, notes and planned/result separation. It looks past blank gaps to detect omitted rows. Unclassified trailing reference sections, formulas or unsupported audit cases remain technical blockers; it does not independently understand free-form coaching intent.
- The **output audit** reads the unpublished workbook and compares every prescribed cell, note, exercise, cycle/day count, native superset, metadata value and cleared inactive set against the reviewed model. The existing writer also checks unrelated OOXML parts and source/template integrity. A failed audit never creates a deliverable.

Candidates stay temporary until all blocks finish and protected source/template/config/manifest/evidence hashes still match. Input drift stops remaining work and invalidates the run; no candidate from that invalidated run is offered. Existing runs, inputs and prior outputs are never overwritten. The JSON retains all diagnostics; the Markdown consolidates duplicate missing-mapping diagnostics and distinguishes decisions from technical findings. Different prescriptions or resolved custom identities are not silently combined into one approval.

## Manual import evidence

The manual-import plan selects representatives for uncovered structural families/features, custom or block-only identities, and always the newest selected program. Families distinguish workbook layout, per-day exercise counts and cycle duration. A blocked newest block is reported, not replaced with an older one. Distinct structures may still require multiple imports; sampling is not proof that untested files will import.

After an actual successful manual import, an optional `manual_import_evidence` list can contain objects with `output` (the exact tested file), `sha256` (its full lowercase SHA-256) and `confirmed: true`. The file hash must match before the run starts. Never add this declaration for an untested candidate. Evidence can reduce redundant structural/identity samples, but **every new output still has `manual_import_verified: false`**. No API, phone automation, scheduled monitor or production spreadsheet runtime is involved. Desktop integration remains a separate slice.
