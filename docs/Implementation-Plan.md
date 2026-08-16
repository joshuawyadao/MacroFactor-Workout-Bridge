# Plan

Build the first local MVP that transfers MacroFactor exercise-log results into a selected week of a coach workbook while preserving the source files and workbook structure. The implementation will use a dependency-light Python CLI, configuration-driven exercise mapping and formatting, OOXML-safe copy-on-write updates, and anonymized end-to-end fixtures.

## Scope
- In: MacroFactor CSV/XLSX exercise-log import, coach worksheet/week discovery, preview and explicit apply flows, exact/alias-first matching, configurable per-exercise conversions and `s` suffixes, advanced set formatting, safety reports, anonymized tests, README, and workbook-integrity validation.
- Out: coach workbook to MacroFactor program import, general machine/dumbbell conversion heuristics, automatic inference that an absent workout was skipped, edits to personal source files, hosted/web UI, and direct changes to `main`.

## Action items
- [x] Record the workbook/export conventions observed in the read-only references and publish approved tracer-bullet GitHub issues [#1](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/issues/1), [#2](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/issues/2), and [#3](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/issues/3).
- [x] Add Python project packaging, CLI entry points, and configuration schemas for aliases, worksheet exercise columns, weight multipliers, and independent suffix formatting.
- [x] Implement MacroFactor CSV/XLSX parsing, week/date filtering, zero-rep rejection, set grouping, and standard/myo/mini/drop/superset result formatting.
- [x] Implement coach worksheet/week discovery and exact configured matching with explicit unmatched and ambiguous outcomes instead of unsafe fuzzy guesses.
- [x] Implement preview and copy-on-write apply behavior that updates only empty result cells by default and preserves formulas, styles, merged cells, relationships, and unrelated workbook parts.
- [x] Add structured terminal and JSON reporting for proposed writes, occupied-cell skips, unmatched/ambiguous exercises, zero-rep rows, unsupported rows, and source/output hashes.
- [x] Add small anonymized XLSX fixtures plus CSV/XLSX automated tests covering formatting, conversions, matching, dynamic worksheet/week discovery, preservation, and source immutability.
- [x] Add README installation, commands, safety behavior, configuration examples, known limitations, and explicit reverse-workflow exclusion.
- [x] Run the full test suite and workbook validation, visually inspect every sheet in the generated anonymized workbook with the spreadsheet tooling, update this plan to completed state, and save the feature branch for review.

## Open questions
- None; the MVP will use conservative defaults and require explicit configuration wherever the references do not establish a safe mapping.

## Verification
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — 13 tests passed.
- `python3 -m compileall -q src tests` — passed.
- Editable install and `macrofactor-bridge --help` — passed in a temporary Python 3.11 environment with local build tooling.
- Anonymized apply validation — six writes created; coach source and MacroFactor export hashes unchanged; all unrelated workbook ZIP members byte-identical.
- Spreadsheet inspection — key values/formulas correct; no formula error tokens found; all generated workbook sheets rendered and visually checked.
- Read-only personal reference inspection — all expected worksheets and week/result columns discovered without modifying the Downloads files.
