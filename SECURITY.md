# Security policy

## Supported version

Security fixes are applied to the latest commit on `main`. This project distributes source for local builds rather than supported release binaries or a hosted service.

## Reporting a vulnerability

Please use [GitHub private vulnerability reporting](https://github.com/joshuawyadao/MacroFactor-Workout-Bridge/security/advisories/new) so details are not disclosed before a fix is available.

Include:

- The affected component, operating system, and Python version.
- Reproduction steps or a minimal proof of concept using synthetic files.
- The likely impact, especially for source-file mutation, overwrite protections, workbook integrity, path disclosure, dependency compromise, or unintended network access.
- Any suggested remediation.

Do not include real MacroFactor exports, coach workbooks, workout history, generated reports, credentials, access tokens, signing material, or unredacted machine-specific paths. Use synthetic examples and redact identifying metadata.

If private vulnerability reporting is unavailable, open a public issue that contains no exploit or sensitive details and ask for a private contact channel.

## Scope

Reports about credential or private-data exposure, unsafe file handling, workbook corruption, dependency compromise, CI privilege expansion, and unauthorized changes to the official repository are in scope. General support questions and feature requests should use regular GitHub issues.
