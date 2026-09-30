# Documentation

[Project home](../README.md)

Start with the task you want to complete. Commands run from the repository root unless a guide says otherwise; quoted names and dates are examples to replace with your own selections.

## Using the bridge

| Guide | What you will find |
| --- | --- |
| [Getting started](Getting-Started.md) | Requirements, first build, private mapping, source files and a synthetic CLI trial |
| [Desktop guide](Desktop-Guide.md) | Dashboard navigation, weekly feedback, workbook transfer and chart interpretation |
| [Local file workflow](Local-File-Workflow.md) | Intake, archives, current links, backup, irregular history layouts and output safety |
| [Configuration](Configuration.md) | Exact aliases, per-side weights, workbook discovery and program policy defaults |
| [CLI reference](CLI-Reference.md) | All commands, write effects, transfer examples, result formatting and exit codes |
| [Troubleshooting](Troubleshooting.md) | Setup, matching, history, output and program blockers |

## Advanced program workflows

| Guide | What you will find |
| --- | --- |
| [Program generation](Program-Generation.md) | Single-block preview, guarded corrections, native set types, template limits and manual import |
| [Batch program review](Program-Batch.md) | Shared/scoped profiles, strict manifest, independent audits and import evidence |

These workflows create candidate program files. They do not import into MacroFactor or establish compatibility automatically.

## Working on the project

| Guide | What you will find |
| --- | --- |
| [Contributing](../CONTRIBUTING.md) | Change scope, privacy rules and PR expectations |
| [Architecture](Architecture.md) | Source ownership, data flow and safety boundaries |
| [Development](Development.md) | Source setup, tests, dependency locks, packaging and CI |
| [Security policy](../SECURITY.md) | Private vulnerability reporting |
| [Code of conduct](../CODE_OF_CONDUCT.md) | Community expectations and private conduct reporting |
| [Regression validation record](Regression-Validation.md) | Historical September 2026 GUI cleanup evidence, not the current test count |
| [Implementation plan](Implementation-Plan.md) | The current branch's work plan and validation record, not a product roadmap |

## Terms used in the guides

| Term | Meaning |
| --- | --- |
| Exercise-log export | Completed workout sets from MacroFactor; used by history and Part 1 |
| Coach workbook | The source `.xlsx` with planned weeks and completed-result cells |
| Mapping | Private JSON connecting exact export/coach names and confirmed load conversions |
| Part 1 | Completed MacroFactor sets → new coach workbook copy |
| Part 2 | Coach prescriptions + direct program template → candidate MacroFactor program |
| Direct program template | A separate `.xlsx` made with Export Program; an exercise log is not a substitute |
| Annotation | Explicitly saved local block dates and training context |
| Current link | A stable local shortcut to a validated archive file for weekly transfer |
| Block / cycle | A discovered coach program section / a repeated program week in Part 2 |
| RIR / estimated 1RM | Repetitions in reserve / a descriptive one-repetition maximum estimate |
